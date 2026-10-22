"""The AI nodes (eaos/studio/nodes) as a job any assistant starts through MCP (run_nodes), any of them at any time: the
same nodes the Studio's action runs, with the person's chosen assistant, the Studio's data published again after."""
from . import agent_tools, guided
from .pipeline.stages import STAGES
from .studio import nodes


def start(project=None, names=None, fresh=False):
    return agent_tools._start('run_nodes', agent_tools.project_state(project), {'nodes': names, 'fresh': fresh}, runner='eaos.node_jobs')


def _job(project, arguments, progress):
    from .studio.actions.adapters import installed
    state = guided.load(project)
    chosen, adapters = guided.chosen_assistant(state), installed()
    records = nodes.run(guided.report_of(state), names=arguments.get('nodes'), adapters={chosen: adapters[chosen]} if chosen in adapters else adapters,
                        project=project, lang=state.get('lang') or 'en', fresh=bool(arguments.get('fresh')))
    guided.publish(state)
    # the plan's stage that reads a node's decisions runs again with them (its answers are cached: no second ask)
    reading = sorted({s.name for name in records for s in STAGES if nodes.BY_NAME[name].produces and nodes.BY_NAME[name].produces[0] in s.produces})
    return {'nodes': nodes.summary(records), 'again_from': reading,
            'what_now': 'Call audit with again_from (each stage named) so the plan reads the decisions, then tell the person what changed.'}


JOBS = {'run_nodes': _job}
