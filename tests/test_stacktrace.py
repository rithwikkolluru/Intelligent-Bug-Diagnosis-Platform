from __future__ import annotations

from app.services.stacktrace import detect_and_split


def test_python_trace_detected():
    text = '''Traceback (most recent call last):
  File "/app/main.py", line 20, in <module>
    raise ValueError("boom")
ValueError: boom'''
    description, trace, lang = detect_and_split(text)
    assert lang == 'Python'
    assert 'Traceback' in trace
    assert 'ValueError: boom' in trace


def test_java_trace_detected():
    text = '''java.lang.NullPointerException
    at com.example.Service.login(Service.java:42)
    at com.example.Controller.handle(Controller.java:18)
Caused by: java.lang.IllegalStateException'''
    description, trace, lang = detect_and_split(text)
    assert lang == 'Java'
    assert 'NullPointerException' in trace


def test_js_trace_detected():
    text = '''Error: Cannot read property 'x' of undefined
    at fn (app.js:10:5)
    at main (index.js:3:2)'''
    description, trace, lang = detect_and_split(text)
    assert lang == 'JavaScript'
    assert 'app.js:10:5' in trace


def test_gdb_trace_detected():
    text = '''#0 0x1234 in process_job () at worker.c:12
#1 0x5678 in main () at main.c:99'''
    description, trace, lang = detect_and_split(text)
    assert lang == 'C/C++'
    assert '#0 0x1234' in trace


def test_no_stack_trace_keeps_text():
    text = 'The service is failing from a bad config and no stack trace was provided.'
    description, trace, lang = detect_and_split(text)
    assert description == text
    assert trace is None
    assert lang is None
