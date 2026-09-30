from .director.timeline import DirectorPlusTimeline
from .engine.director_long import DirectorPlusGenerate, DirectorPlusVideoOutput
from .engine.director_lbh import DirectorPlusConditioningMatchLatent
from .engine import director_project
from .director import refmod_library
from .director import refmod_create
from .director import h3_forge  # registers /director_plus/dasiwa/h3/forge routes
from . import prompt_director_compat  # lets PromptDirector FOLLOW_DIRECTOR see DirectorPlusTimeline
from server import PromptServer

refmod_library.register_routes(PromptServer.instance)
refmod_create.register_routes(PromptServer.instance)

NODE_CLASS_MAPPINGS = {
    "DirectorPlusConditioningMatchLatent": DirectorPlusConditioningMatchLatent,
    "DirectorPlusTimeline": DirectorPlusTimeline,
    "DirectorPlusGenerate": DirectorPlusGenerate,
    "DirectorPlusVideoOutput": DirectorPlusVideoOutput,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DirectorPlusConditioningMatchLatent": "Director Plus · Match LBH Conditioning",
    "DirectorPlusTimeline": "MiniMax H3 Director Plus",
    "DirectorPlusGenerate": "Director Plus · Generate",
    "DirectorPlusVideoOutput": "Director Plus · Video Output",
}
WEB_DIRECTORY = "./web"
