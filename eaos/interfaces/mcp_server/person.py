"""What only the person decides, for every MCP tool (the server's, the governance tools, the rules tools) and the
terminal: these tools, and these operations of the tools and commands that group them. In a run the Studio started
(EAOS_STUDIO_RUN set by eaos/interfaces/studio_actions) the assistant asks instead, and the person answers in the
Studio, which calls these itself."""
import os

PERSON_ONLY = ('accept', 'undo', 'choose_branch', 'answer', 'branches merge', 'branches delete', 'branches protect', 'branches cleanup',
               'branches restore', 'auto_accept', 'sign_in_forget', 'logic_flaws', 'rule pin', 'rule unpin', 'rule change', 'rule hook',
               'rule approve')
STUDIO = 'EAOS Studio'           # the name the Studio's own calls are recorded under


def refuse_in_studio_run(name):
    """PermissionError for a decision only the person makes (PERSON_ONLY), asked inside a run the Studio started."""
    if name in PERSON_ONLY and os.environ.get('EAOS_STUDIO_RUN'):
        raise PermissionError(f"{name} is the person's decision, and they make it in the EAOS Studio: ask them with an "
                              'eaos-question block and stop')
