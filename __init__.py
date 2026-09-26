from .director.timeline import DirectorPlusTimeline
from .engine.director_long import DirectorPlusGenerate, DirectorPlusVideoOutput
from .engine import director_project
from .director import refmod_library
from server import PromptServer

refmod_library.register_routes(PromptServer.instance)

NODE_CLASS_MAPPINGS = {
    "DirectorPlusTimeline": DirectorPlusTimeline,
    "DirectorPlusGenerate": DirectorPlusGenerate,
    "DirectorPlusVideoOutput": DirectorPlusVideoOutput,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DirectorPlusTimeline": "MiniMax H3 Director Plus",
    "DirectorPlusGenerate": "Director Plus · Generate",
    "DirectorPlusVideoOutput": "Director Plus · Video Output",
}
WEB_DIRECTORY = "./web"
