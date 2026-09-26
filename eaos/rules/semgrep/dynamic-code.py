import ast


def run(text):
    # ruleid: eaos.security.dynamic-code-python
    eval(text)
    # ruleid: eaos.security.dynamic-code-python
    exec(text)
    # ok: eaos.security.dynamic-code-python
    return ast.literal_eval(text)
