from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.base import AgentInput
from app.agents.log_analysis.agent import LogAnalysisAgent, compute_log_confidence
from app.agents.log_analysis.heuristics import is_application_code, unescape_log_text
from app.agents.log_analysis.parsers import (
    AndroidLogcatParser,
    CppGdbLogParser,
    DotNetLogParser,
    GenericLogParser,
    GoLogParser,
    JavaLogParser,
    JavaScriptFirefoxLogParser,
    JavaScriptV8LogParser,
    PythonLogParser,
    detect_best_parser,
)
from app.agents.log_analysis.schemas import (
    ConfidenceBreakdown,
    ExceptionInfo,
    FailurePoint,
    LogAnalysisResult,
)
from app.llm.client import FakeLLMClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "logs"


# ============================================================================
# 1. Paired Fixture Tests
# ============================================================================
@pytest.mark.parametrize(
    "log_name,expected_name",
    [
        ("java_npe.log", "java_npe_expected.json"),
        ("python_keyerror.log", "python_keyerror_expected.json"),
        ("javascript_v8.log", "javascript_v8_expected.json"),
        ("javascript_firefox.log", "javascript_firefox_expected.json"),
        ("cpp_gdb.log", "cpp_gdb_expected.json"),
        ("dotnet.log", "dotnet_expected.json"),
        ("go_panic.log", "go_panic_expected.json"),
        ("android_logcat.log", "android_logcat_expected.json"),
        ("generic_error.log", "generic_error_expected.json"),
        ("html_escaped.log", "html_escaped_expected.json"),
    ],
)
def test_fixture_parsing(log_name: str, expected_name: str):
    log_file = FIXTURES_DIR / log_name
    expected_file = FIXTURES_DIR / expected_name

    assert log_file.exists(), f"Missing fixture {log_name}"
    assert expected_file.exists(), f"Missing expected fixture {expected_name}"

    log_text = log_file.read_text(encoding="utf-8")
    expected = json.loads(expected_file.read_text(encoding="utf-8"))

    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    result = agent.run(AgentInput(stack_trace=log_text))

    assert result.status == "ok"
    assert result.output is not None
    out = result.output

    assert out.detected_format == expected["detected_format"]
    if "exception_type" in expected:
        assert expected["exception_type"] in (out.exception_type.fully_qualified, out.exception_type.simple_name)
    if "failure_point_file" in expected and out.failure_point:
        assert expected["failure_point_file"] in (out.failure_point.file or "")
    if "failure_point_line" in expected and out.failure_point:
        assert out.failure_point.line == expected["failure_point_line"]
    if "is_application_code" in expected and out.failure_point:
        assert out.failure_point.is_application_code == expected["is_application_code"]


# ============================================================================
# 2. Java Parser Detailed Unit Tests (8 tests)
# ============================================================================
def test_java_parser_basic_npe():
    trace = (
        "java.lang.NullPointerException: Cannot invoke method on null\n"
        "    at com.example.service.OrderService.process(OrderService.java:42)\n"
        "    at com.example.controller.OrderController.submit(OrderController.java:15)"
    )
    parser = JavaLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "NullPointerException"
    assert out.error_message == "Cannot invoke method on null"
    assert out.failure_point is not None
    assert out.failure_point.file == "OrderService.java"
    assert out.failure_point.line == 42


def test_java_parser_caused_by_chain():
    trace = (
        "org.springframework.web.util.NestedServletException: Request processing failed\n"
        "    at org.springframework.web.servlet.FrameworkServlet.processRequest(FrameworkServlet.java:1014)\n"
        "Caused by: java.sql.SQLException: Connection timeout\n"
        "    at com.example.dao.UserDao.find(UserDao.java:88)\n"
        "    ... 24 more"
    )
    parser = JavaLogParser()
    out = parser.parse(trace)
    assert len(out.exception_chain) == 2
    assert out.root_cause_exception is not None
    assert out.root_cause_exception.type == "java.sql.SQLException"
    assert out.failure_point is not None
    assert out.failure_point.file == "UserDao.java"
    assert out.failure_point.line == 88


def test_java_parser_native_method():
    trace = (
        "java.lang.OutOfMemoryError: Java heap space\n"
        "    at java.lang.Object.clone(Native Method)\n"
        "    at com.example.buffer.BufferManager.allocate(BufferManager.java:30)"
    )
    parser = JavaLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    # Skips native method for app frame
    assert out.failure_point.file == "BufferManager.java"
    assert out.failure_point.line == 30


def test_java_parser_unknown_source():
    trace = (
        "java.lang.RuntimeException: Unhandled\n"
        "    at com.example.ThirdParty.run(Unknown Source)\n"
        "    at com.mycompany.app.Main.start(Main.java:12)"
    )
    parser = JavaLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == "Main.java"
    assert out.failure_point.line == 12


def test_java_parser_lambda_expressions():
    trace = (
        "java.lang.IllegalArgumentException: Invalid item\n"
        "    at com.example.service.ItemProcessor$$Lambda$42/0x0000000800c01200.accept(Unknown Source)\n"
        "    at com.example.service.ItemProcessor.processAll(ItemProcessor.java:75)"
    )
    parser = JavaLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == "ItemProcessor.java"
    assert out.failure_point.line == 75


def test_java_parser_suppressed_exceptions():
    trace = (
        "java.io.IOException: Stream closed\n"
        "    at com.example.io.Reader.read(Reader.java:50)\n"
        "Suppressed: java.io.IOException: Failed to close resource\n"
        "    at com.example.io.Reader.close(Reader.java:70)"
    )
    parser = JavaLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "IOException"
    assert len(out.frames) >= 1


def test_java_parser_thread_header():
    trace = (
        'Exception in thread "main" java.lang.ArrayIndexOutOfBoundsException: Index 5 out of bounds for length 5\n'
        "    at com.example.ArrayApp.main(ArrayApp.java:10)"
    )
    parser = JavaLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "ArrayIndexOutOfBoundsException"
    assert out.failure_point is not None
    assert out.failure_point.file == "ArrayApp.java"
    assert out.failure_point.line == 10


def test_java_parser_detection_score():
    parser = JavaLogParser()
    trace = "java.lang.NullPointerException\n    at com.example.Foo.bar(Foo.java:10)"
    assert parser.detect(trace) >= 0.5
    assert parser.detect("random non java logs") < 0.2


# ============================================================================
# 3. Python Parser Detailed Unit Tests (8 tests)
# ============================================================================
def test_python_parser_standard_traceback():
    trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/main.py", line 25, in run\n'
        "    result = calculate()\n"
        '  File "/app/calc.py", line 50, in calculate\n'
        "    return 10 / 0\n"
        "ZeroDivisionError: division by zero"
    )
    parser = PythonLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "ZeroDivisionError"
    assert out.error_message == "division by zero"
    assert out.failure_point is not None
    assert out.failure_point.file == "/app/calc.py"
    assert out.failure_point.line == 50


def test_python_parser_chained_during_handling():
    trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/service.py", line 10, in connect\n'
        "    raise ConnectionError('db down')\n"
        "ConnectionError: db down\n\n"
        "During handling of the above exception, another exception occurred:\n\n"
        "Traceback (most recent call last):\n"
        '  File "/app/handler.py", line 40, in handle\n'
        "    log_failure()\n"
        "KeyError: 'logger'"
    )
    parser = PythonLogParser()
    out = parser.parse(trace)
    assert len(out.exception_chain) == 2
    assert out.exception_type.simple_name == "KeyError"
    assert out.failure_point is not None
    assert out.failure_point.file == "/app/handler.py"
    assert out.failure_point.line == 40


def test_python_parser_chained_direct_cause():
    trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/io.py", line 12, in read_data\n'
        "    raw = fetch()\n"
        "ValueError: invalid format\n\n"
        "The above exception was the direct cause of the following exception:\n\n"
        "Traceback (most recent call last):\n"
        '  File "/app/api.py", line 85, in endpoint\n'
        "    data = read_data()\n"
        "RuntimeError: Failed to process payload"
    )
    parser = PythonLogParser()
    out = parser.parse(trace)
    assert len(out.exception_chain) == 2
    assert out.exception_type.simple_name == "RuntimeError"


def test_python_parser_frozen_importlib():
    trace = (
        "Traceback (most recent call last):\n"
        '  File "<frozen importlib._bootstrap>", line 983, in _find_and_load\n'
        '  File "/app/main.py", line 5, in <module>\n'
        "    import missing_module\n"
        "ModuleNotFoundError: No module named 'missing_module'"
    )
    parser = PythonLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    # Topmost application frame is chosen over <frozen>
    assert out.failure_point.file == "/app/main.py"
    assert out.failure_point.line == 5


def test_python_parser_string_evaluation():
    trace = (
        "Traceback (most recent call last):\n"
        '  File "<string>", line 1, in <module>\n'
        "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
    )
    parser = PythonLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "TypeError"
    assert out.failure_point is not None
    assert out.failure_point.file == "<string>"
    assert out.failure_point.line == 1


def test_python_parser_syntax_error():
    trace = (
        '  File "/app/script.py", line 12\n'
        "    def invalid syntax:\n"
        "                   ^\n"
        "SyntaxError: invalid syntax"
    )
    parser = PythonLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "SyntaxError"
    assert out.failure_point is not None
    assert out.failure_point.file == "/app/script.py"
    assert out.failure_point.line == 12


def test_python_parser_multi_line_error_message():
    trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/worker.py", line 33, in execute\n'
        "    assert a == b\n"
        "AssertionError: Expected value 10\n"
        "to equal 20"
    )
    parser = PythonLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "AssertionError"


def test_python_parser_detection():
    parser = PythonLogParser()
    assert parser.detect('Traceback (most recent call last):\n  File "x.py", line 1') >= 0.7
    assert parser.detect("random line") < 0.2


# ============================================================================
# 4. JavaScript V8 Parser Tests (6 tests)
# ============================================================================
def test_js_v8_async_call():
    trace = (
        "Error: Network timeout\n"
        "    at async fetchWithRetry (src/api/client.js:42:15)\n"
        "    at async DataLoader.load (src/data/loader.js:88:5)"
    )
    parser = JavaScriptV8LogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "Error"
    assert out.failure_point is not None
    assert out.failure_point.file == "src/api/client.js"
    assert out.failure_point.line == 42


def test_js_v8_new_constructor():
    trace = (
        "TypeError: Missing required prop\n"
        "    at new UserProfile (src/models/user.js:15:9)\n"
        "    at parseUser (src/parser.js:20:12)"
    )
    parser = JavaScriptV8LogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == "src/models/user.js"
    assert out.failure_point.line == 15


def test_js_v8_anonymous_and_eval():
    trace = (
        "RangeError: Maximum call stack size exceeded\n"
        "    at eval (eval at execute (src/evaluator.js:10:5), <anonymous>:1:20)\n"
        "    at execute (src/evaluator.js:10:5)"
    )
    parser = JavaScriptV8LogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "RangeError"
    assert out.failure_point is not None
    assert out.failure_point.file == "src/evaluator.js"


def test_js_v8_skips_node_modules():
    trace = (
        "ReferenceError: window is not defined\n"
        "    at Object.<anonymous> (node_modules/library/dist/index.js:450:12)\n"
        "    at App (src/App.jsx:12:3)"
    )
    parser = JavaScriptV8LogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    # App.jsx is application code, selected over node_modules
    assert out.failure_point.file == "src/App.jsx"
    assert out.failure_point.line == 12


def test_js_v8_minified_single_line():
    trace = "Error: fail at a (app.min.js:1:100) at b (app.min.js:1:200)"
    parser = JavaScriptV8LogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "Error"


def test_js_v8_detection():
    parser = JavaScriptV8LogParser()
    assert parser.detect("TypeError: fail\n    at render (App.js:10:2)") >= 0.5


# ============================================================================
# 5. JavaScript Firefox Tests (4 tests)
# ============================================================================
def test_js_firefox_basic():
    trace = (
        "TypeError: item is null\n"
        "process@http://localhost:3000/main.js:15:3\n"
        "start@http://localhost:3000/app.js:5:1"
    )
    parser = JavaScriptFirefoxLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "TypeError"
    assert out.failure_point is not None
    assert out.failure_point.file == "http://localhost:3000/main.js"
    assert out.failure_point.line == 15
    assert out.failure_point.column == 3


def test_js_firefox_anonymous():
    trace = (
        "@http://localhost:3000/inline.js:42:10\n"
        "dispatch@http://localhost:3000/event.js:10:2"
    )
    parser = JavaScriptFirefoxLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.line == 42


def test_js_firefox_local_path():
    trace = "fn@/var/www/app/script.js:100:5"
    parser = JavaScriptFirefoxLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == "/var/www/app/script.js"
    assert out.failure_point.line == 100


def test_js_firefox_detection():
    parser = JavaScriptFirefoxLogParser()
    assert parser.detect("foo@http://site.com/app.js:1:2\nbar@http://site.com/app.js:3:4") >= 0.5


# ============================================================================
# 6. C/C++ GDB & Sanitizer Tests (6 tests)
# ============================================================================
def test_cpp_gdb_frames():
    trace = (
        "#0  0x00007ffff7a24c37 in __GI_raise () at raise.c:51\n"
        "#1  0x00007ffff7a26028 in __GI_abort () at abort.c:79\n"
        "#2  0x0000000000401824 in CacheBuffer::release () at cache_buffer.cpp:112"
    )
    parser = CppGdbLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == "cache_buffer.cpp"
    assert out.failure_point.line == 112


def test_cpp_gdb_template_demangling():
    trace = "#0  0x0000000000402100 in std::vector<int, std::allocator<int> >::at(unsigned long) at /usr/include/c++/vector:1040"
    parser = CppGdbLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert "vector" in (out.failure_point.file or "")


def test_cpp_gdb_signal_header():
    trace = (
        "Program received signal SIGSEGV, Segmentation fault.\n"
        "#0  0x0000000000401000 in crash_func () at main.cpp:20"
    )
    parser = CppGdbLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "SIGSEGV"
    assert out.failure_point is not None
    assert out.failure_point.file == "main.cpp"
    assert out.failure_point.line == 20


def test_cpp_sanitizer_output():
    trace = (
        "ERROR: AddressSanitizer: heap-use-after-free on address 0x603000000010\n"
        "#0 0x401824 in FreeBuffer at buffer.cpp:50"
    )
    parser = CppGdbLogParser()
    out = parser.parse(trace)
    assert "AddressSanitizer" in out.exception_type.simple_name
    assert out.failure_point is not None
    assert out.failure_point.file == "buffer.cpp"


def test_cpp_skips_glibc_frames():
    trace = (
        "#0  0x00007f in __libc_start_main () at /usr/lib/libc.so:10\n"
        "#1  0x000040 in main () at src/server.cpp:35"
    )
    parser = CppGdbLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == "src/server.cpp"
    assert out.failure_point.line == 35


def test_cpp_detection():
    parser = CppGdbLogParser()
    assert parser.detect("#0 0x123 in foo () at main.c:10\n#1 0x456 in bar () at main.c:20") >= 0.6


# ============================================================================
# 7. .NET / C# Tests (4 tests)
# ============================================================================
def test_dotnet_null_ref():
    trace = (
        "System.NullReferenceException: Object reference not set to an instance of an object.\n"
        r"   at App.Services.AuthService.Login(String user) in C:\App\AuthService.cs:line 55"
    )
    parser = DotNetLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "NullReferenceException"
    assert out.failure_point is not None
    assert "AuthService.cs" in (out.failure_point.file or "")
    assert out.failure_point.line == 55


def test_dotnet_async_state_machine():
    trace = (
        "System.InvalidOperationException: Sequence contains no elements\n"
        r"   at App.Handlers.OrderHandler.<ProcessAsync>d__3.MoveNext() in C:\App\OrderHandler.cs:line 102"
    )
    parser = DotNetLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.line == 102


def test_dotnet_skips_system_assemblies():
    trace = (
        "System.ArgumentException: Arg invalid\n"
        "   at System.ThrowHelper.ThrowArgumentException()\n"
        r"   at App.Validator.Validate() in C:\App\Validator.cs:line 20"
    )
    parser = DotNetLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == r"C:\App\Validator.cs"


def test_dotnet_detection():
    parser = DotNetLogParser()
    assert parser.detect("System.NullReferenceException: err\n   at Foo.Bar() in C:\\f.cs:line 1") >= 0.7


# ============================================================================
# 8. Go Parser Tests (4 tests)
# ============================================================================
def test_go_panic_index():
    trace = (
        "panic: runtime error: index out of range [10] with length 5\n\n"
        "goroutine 1 [running]:\n"
        "main.getElement(0x10)\n"
        "\t/app/slice.go:24 +0x30"
    )
    parser = GoLogParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "panic"
    assert out.failure_point is not None
    assert out.failure_point.file == "/app/slice.go"
    assert out.failure_point.line == 24


def test_go_panic_nil_dereference():
    trace = (
        "panic: runtime error: invalid memory address or nil pointer dereference\n\n"
        "goroutine 1 [running]:\n"
        "github.com/example/pkg.Execute()\n"
        "\t/go/src/github.com/example/pkg/runner.go:90 +0x12"
    )
    parser = GoLogParser()
    out = parser.parse(trace)
    assert "nil pointer dereference" in out.error_message
    assert out.failure_point is not None
    assert out.failure_point.file == "/go/src/github.com/example/pkg/runner.go"


def test_go_skips_runtime_frames():
    trace = (
        "panic: abort\n"
        "goroutine 1 [running]:\n"
        "runtime.gopanic()\n"
        "\t/usr/local/go/src/runtime/panic.go:88\n"
        "main.myFunc()\n"
        "\t/app/main.go:15"
    )
    parser = GoLogParser()
    out = parser.parse(trace)
    assert out.failure_point is not None
    assert out.failure_point.file == "/app/main.go"


def test_go_detection():
    parser = GoLogParser()
    assert parser.detect("panic: runtime error\ngoroutine 1 [running]:") >= 0.8


# ============================================================================
# 9. Android Logcat Tests (3 tests)
# ============================================================================
def test_android_logcat_detection():
    trace = "11-22 10:00:00.123 100 100 E AndroidRuntime: FATAL EXCEPTION: main"
    parser = AndroidLogcatParser()
    assert parser.detect(trace) >= 0.9


def test_android_logcat_parsing():
    trace = (
        "11-22 10:00:00.123 100 100 E AndroidRuntime: FATAL EXCEPTION: main\n"
        "11-22 10:00:00.123 100 100 E AndroidRuntime: java.lang.SecurityException: Permission denied\n"
        "11-22 10:00:00.123 100 100 E AndroidRuntime: \tat com.example.app.CameraActivity.open(CameraActivity.java:100)"
    )
    parser = AndroidLogcatParser()
    out = parser.parse(trace)
    assert out.detected_format == "android_logcat"
    assert out.exception_type.simple_name == "SecurityException"
    assert out.failure_point is not None
    assert out.failure_point.file == "CameraActivity.java"


def test_android_logcat_process_header():
    trace = (
        "E/AndroidRuntime: Process: com.my.game, PID: 4567\n"
        "E/AndroidRuntime: java.lang.OutOfMemoryError: GL buffer allocation failed\n"
        "E/AndroidRuntime: \tat com.my.game.Renderer.init(Renderer.java:50)"
    )
    parser = AndroidLogcatParser()
    out = parser.parse(trace)
    assert out.exception_type.simple_name == "OutOfMemoryError"


# ============================================================================
# 10. Generic Log Parser Tests (4 tests)
# ============================================================================
def test_generic_log_error_extraction():
    log = (
        "2026-11-22 INFO Starting server on port 8080\n"
        "2026-11-22 WARN High memory usage: 85%\n"
        "2026-11-22 ERROR DatabaseError: Connection pool exhausted after 30000ms"
    )
    parser = GenericLogParser()
    out = parser.parse(log)
    assert "DatabaseError" in out.error_message
    assert out.detected_format == "generic_log"


def test_generic_log_repeated_lines():
    log = (
        "2026-11-22 ERROR Failed to write record #101\n"
        "2026-11-22 ERROR Failed to write record #101\n"
        "2026-11-22 ERROR Failed to write record #101"
    )
    parser = GenericLogParser()
    out = parser.parse(log)
    assert any("REPEATED_ERROR_LINE" in w for w in out.warnings)


def test_generic_log_detection():
    parser = GenericLogParser()
    assert parser.detect("2026-11-22 CRITICAL Out of disk space") >= 0.3


def test_generic_log_no_error_fallback():
    parser = GenericLogParser()
    out = parser.parse("Just plain informational text without keywords")
    assert out.detected_format == "generic_log"


# ============================================================================
# 11. Confidence Formula Tests (4 tests)
# ============================================================================
def test_confidence_full_signals():
    breakdown = ConfidenceBreakdown(
        exception_type_parsed=True,
        error_message_extracted=True,
        frames_parsed_count=5,
        line_numbers_present=True,
        application_frame_found=True,
        chain_consistent=True,
        parser_fully_consumed=True,
        llm_fallback_used=False,
    )
    score = compute_log_confidence(breakdown)
    assert score == 1.0


def test_confidence_capped_with_llm_fallback():
    breakdown = ConfidenceBreakdown(
        exception_type_parsed=True,
        error_message_extracted=True,
        frames_parsed_count=5,
        line_numbers_present=True,
        application_frame_found=True,
        chain_consistent=True,
        parser_fully_consumed=True,
        llm_fallback_used=True,  # Cap at 0.75
    )
    score = compute_log_confidence(breakdown)
    assert score == 0.75


def test_confidence_partial_when_line_numbers_missing():
    breakdown = ConfidenceBreakdown(
        exception_type_parsed=True,
        error_message_extracted=True,
        frames_parsed_count=1,
        line_numbers_present=False,
        application_frame_found=False,
        chain_consistent=False,
    )
    score = compute_log_confidence(breakdown)
    assert score == 0.5


def test_confidence_zero_on_empty():
    score = compute_log_confidence(ConfidenceBreakdown())
    assert score == 0.0


# ============================================================================
# 12. Application Code Heuristic & Code Path Order (7 tests)
# ============================================================================
def test_is_application_code_helper():
    assert is_application_code("com/mycompany/Service.java", "com.mycompany.Service") is True
    assert is_application_code("org/springframework/web/Dispatcher.java", "org.springframework.web") is False
    assert is_application_code("node_modules/express/index.js", "express") is False
    assert is_application_code("/usr/lib/libc.so", "libc") is False


def test_java_code_path_order_is_entry_to_failure():
    # In raw Java, top frame is OrderService.java (failure).
    # Normalized code_path MUST have entry point (Controller) first, failure (Service) last!
    trace = (
        "java.lang.NullPointerException: boom\n"
        "    at com.example.service.OrderService.fail(OrderService.java:50)\n"
        "    at com.example.controller.OrderController.entry(OrderController.java:10)"
    )
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(stack_trace=trace))
    assert res.output is not None
    code_path = res.output.code_path
    assert len(code_path) == 2
    assert code_path[0].file == "OrderController.java"
    assert code_path[1].file == "OrderService.java"


def test_python_code_path_order_is_entry_to_failure():
    # Python raw is already entry -> failure. Normalized code_path preserves this.
    trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/main.py", line 10, in entry\n'
        "    call_worker()\n"
        '  File "/app/worker.py", line 40, in call_worker\n'
        "    fail()\n"
        "ValueError: error"
    )
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(stack_trace=trace))
    assert res.output is not None
    code_path = res.output.code_path
    assert code_path[0].file == "/app/main.py"
    assert code_path[1].file == "/app/worker.py"


# ============================================================================
# 13. LLM Fallback & No-Silent-Override Rule (4 tests)
# ============================================================================
def test_no_silent_override_parser_wins_over_conflicting_llm():
    # Parser extracts NullPointerException. LLM suggests IllegalArgumentException.
    # Rule: Parser's NullPointerException MUST be kept, conflict logged in warnings.
    trace = (
        "java.lang.NullPointerException: Null ref\n"
        "    at com.example.App.run(App.java:10)"
    )
    llm_mock_output = LogAnalysisResult(
        detected_format="java",
        exception_type=ExceptionInfo(fully_qualified="java.lang.IllegalArgumentException", simple_name="IllegalArgumentException"),
        error_message="LLM hallucinated message",
        failure_point=FailurePoint(file="Hallucinated.java", line=999),
    )
    agent = LogAnalysisAgent(llm_client=FakeLLMClient(canned_responses=[llm_mock_output]))
    res = agent.run(AgentInput(stack_trace=trace))

    assert res.output is not None
    # Parser exception was preserved
    assert res.output.exception_type.simple_name == "NullPointerException"
    # Failure point from parser was preserved
    assert res.output.failure_point is not None
    assert res.output.failure_point.file == "App.java"


def test_llm_fills_missing_failure_point():
    # Input has an error message but no stack frames
    text = "2026-11-22 ERROR Database connection timed out after 30s"
    llm_output = LogAnalysisResult(
        detected_format="generic_log",
        exception_type=ExceptionInfo(fully_qualified="TimeoutException", simple_name="TimeoutException"),
        error_message="Database connection timed out",
        failure_point=FailurePoint(file="src/db/pool.py", line=45, is_application_code=True),
    )
    agent = LogAnalysisAgent(llm_client=FakeLLMClient(canned_responses=[llm_output]))
    res = agent.run(AgentInput(error_logs=text))

    assert res.output is not None
    assert res.output.failure_point is not None
    assert res.output.failure_point.file == "src/db/pool.py"
    assert res.output.failure_point.line == 45


def test_fallback_when_llm_is_unavailable():
    # When LLM provider is unavailable, parser result is returned with warning
    text = "2026-11-22 ERROR Out of memory"
    agent = LogAnalysisAgent(llm_client=FakeLLMClient(raise_unavailable=True))
    res = agent.run(AgentInput(error_logs=text))

    assert res.status in {"ok", "partial"}
    assert res.output is not None
    assert any("LLM_FALLBACK_SKIPPED" in w for w in res.warnings)


def test_mixed_prose_and_trace_extracted():
    text = (
        "We observed an outage during user checkout.\n"
        "Here is the traceback:\n\n"
        "Traceback (most recent call last):\n"
        '  File "/app/checkout.py", line 20, in pay\n'
        "    charge()\n"
        "RuntimeError: Payment gateway unavailable\n\n"
        "Please look into this ASAP."
    )
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(description=text))
    assert res.status == "ok"
    assert res.output is not None
    assert res.output.exception_type.simple_name == "RuntimeError"
    assert res.output.failure_point is not None
    assert res.output.failure_point.file == "/app/checkout.py"


# ============================================================================
# 14. Edge Cases: Capping, Truncation, Escaping, Garbage (8 tests)
# ============================================================================
def test_edge_case_empty_input():
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput())
    assert res.status == "skipped"
    assert "EMPTY_INPUT" in res.warnings


def test_edge_case_description_only_no_trace():
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(title="Button not working", description="The submit button is blue instead of green."))
    assert res.status == "skipped"
    assert "NO_LOG_OR_STACK_TRACE_DETECTED" in res.warnings


def test_edge_case_truncated_trace_warning():
    trace = (
        "java.lang.NullPointerException: null\n"
        "    at com.example.App.start(App.java:10)\n"
        "    ... 45 more"
    )
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(stack_trace=trace))
    assert res.output is not None
    assert any("TRUNCATED_STACK_TRACE" in w for w in res.warnings)


def test_edge_case_large_trace_capped_at_100():
    frames = "\n".join([f"    at com.example.Class{i}.method(Class{i}.java:{i})" for i in range(150)])
    trace = f"java.lang.StackOverflowError\n{frames}"
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(stack_trace=trace))
    assert res.output is not None
    assert len(res.output.code_path) == 100
    assert any("STACK_TRACE_CAPPED_AT_100_FRAMES" in w for w in res.warnings)


def test_edge_case_binary_garbage_filtered():
    trace = "Traceback (most recent call last):\n\x00\x01\x02  File \"main.py\", line 1\nValueError: bad"
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(stack_trace=trace))
    assert res.output is not None
    assert any("BINARY_OR_UNPRINTABLE_CHARACTERS_FILTERED" in w for w in res.warnings)


def test_edge_case_json_escaped_newlines():
    trace = "java.lang.NullPointerException: err\\n    at com.example.App.run(App.java:15)"
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(stack_trace=trace))
    assert res.output is not None
    assert res.output.exception_type.simple_name == "NullPointerException"
    assert res.output.failure_point is not None
    assert res.output.failure_point.file == "App.java"


def test_edge_case_windows_crlf_paths():
    trace = (
        "System.Exception: Failure\r\n"
        r"   at Service.Worker.Execute() in C:\Users\App\Worker.cs:line 45"
    )
    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    res = agent.run(AgentInput(stack_trace=trace))
    assert res.output is not None
    assert res.output.detected_format == "dotnet"
    assert res.output.failure_point is not None
    assert "Worker.cs" in (res.output.failure_point.file or "")


def test_edge_case_property_input_immutability():
    """Property test: Verifies that the agent NEVER mutates the caller's AgentInput object."""
    orig_title = "Critical NPE"
    orig_desc = "User checkout fails"
    orig_trace = "java.lang.NullPointerException: null\n    at com.example.Pay.now(Pay.java:10)"
    orig_logs = "2026-11-22 ERROR [thread-1] payment failed"

    inp = AgentInput(
        title=orig_title,
        description=orig_desc,
        stack_trace=orig_trace,
        error_logs=orig_logs,
        programming_language="Java",
        project="internal",
    )

    agent = LogAnalysisAgent(llm_client=FakeLLMClient())
    agent.run(inp)

    # Assert completely untouched
    assert inp.title == orig_title
    assert inp.description == orig_desc
    assert inp.stack_trace == orig_trace
    assert inp.error_logs == orig_logs
    assert inp.programming_language == "Java"
    assert inp.project == "internal"
