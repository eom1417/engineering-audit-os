"""Pipelines that run through a message queue, read without running them (eaos/facts/pipeline.py): the functions that
send to a topic and those that read it, linked through the topic they share."""
import ast
from collections import defaultdict

from . import call_name
from .pipeline_read import slug, site, Found, _str, _strs

QUEUE_MODULES = {'kafka', 'confluent_kafka', 'aiokafka', 'pika', 'aio_pika', 'nats', 'redis', 'google'}
PRODUCE_CALLS = ('send', 'produce', 'publish', 'basic_publish', 'xadd')
CONSUME_CALLS = ('subscribe', 'KafkaConsumer', 'basic_consume', 'xread', 'consume')


def _topic_use(sub):
    """('produced', [topic]) or ('consumed', [topics]) for a call that sends to or reads from a queue, else None."""
    callee = call_name(sub.func) or ''
    first = _str(sub.args[0]) if sub.args else None
    keyword = {k.arg: _str(k.value) for k in sub.keywords}
    topic = first or keyword.get('topic') or keyword.get('routing_key')
    if callee in PRODUCE_CALLS and topic: return 'produced', [topic]
    if callee in CONSUME_CALLS and (sub.args or keyword.get('queue')):
        return 'consumed', [t for t in (_strs(sub.args[0]) if sub.args else []) or [keyword.get('queue')] if t]
    return None


def _queue_uses(py):
    """({topic: [(file, function, node, line)]} produced, the same consumed) in the files that import a queue client."""
    uses = {'produced': defaultdict(list), 'consumed': defaultdict(list)}
    for rel, name, node in py.functions():
        modules = {(m or '').split('.')[0] for m, _ in py.imports.get(rel, {}).values()}
        if not modules & QUEUE_MODULES: continue
        for sub in ast.walk(node):
            use = _topic_use(sub) if isinstance(sub, ast.Call) else None
            for topic in (use or (None, []))[1]: uses[use[0]][topic].append((rel, name, node, sub.lineno))
    return uses['produced'], uses['consumed']


def _topic_links(py, found, topic, produced, consumed):
    """Every function on a topic as a stage, and a link from each producer to each consumer."""
    for rel, name, node, line in produced + consumed:
        found.stage(name, site(rel, node.lineno, py.line(rel, node.lineno)), symbol=f"{rel[:-3].replace('/', '.')}.{name}")
    for a in produced:
        for b in consumed:
            found.edge(f'{found.id}/{slug(a[1])}', f'{found.id}/{slug(b[1])}', 'topic', site(b[0], b[3], py.line(b[0], b[3])), names=[topic])


def queues(py, out):
    produced, consumed = _queue_uses(py)
    shared = sorted(set(produced) & set(consumed))
    if not shared: return
    first = produced[shared[0]][0]
    found = Found(f'{first[0]}:topics', 'topics', 'queue', site(first[0], first[3], py.line(first[0], first[3])))
    for topic in shared: _topic_links(py, found, topic, produced[topic], consumed[topic])
    out.append(found)
