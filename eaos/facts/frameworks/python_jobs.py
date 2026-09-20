"""Background jobs and scheduled work."""
import re

LANGUAGES = ('python',)
FILENAMES = ('crontab', 'Crontab')
TASK = re.compile(r'^\s*@(?:shared_task|celery\.task|app\.task|task)\b', re.M)
SCHEDULE = re.compile(r'^\s*@(?:scheduler\.scheduled_job|repeat_every|cron)\b', re.M)
LAMBDA = re.compile(r'^def\s+(lambda_handler|handler)\s*\(', re.M)


def detect(context):
    found = []
    for pattern, framework in [(TASK, 'celery'), (SCHEDULE, 'scheduler')]:
        for match in pattern.finditer(context.text):
            line = context.line_of(match.start())
            handler = context.symbol_after(line)
            found.append({'surface': 'job', 'route': handler, 'http_method': None, 'handler': handler,
                          'framework': framework, 'line': line})
    for match in LAMBDA.finditer(context.text):
        line = context.line_of(match.start())
        found.append({'surface': 'job', 'route': match.group(1), 'http_method': None, 'handler': match.group(1),
                      'framework': 'serverless_handler', 'line': line})
    return found
