"""The AI nodes (eaos/studio/nodes) as a job any assistant starts through MCP (run_nodes), any of them at any time: the
same nodes the Studio's action runs, with the person's chosen assistant, the Studio's data published again after."""
from . import agent_tools, guided
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
    return {'nodes': nodes.summary(records), 'what_now': 'Tell the person what each node decided; what needs them waits in the Decisions inbox.'}


JOBS = {'run_nodes': _job}
