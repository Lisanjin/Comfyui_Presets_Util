import requests
import json
import os
import random

BASE_URL = "http://127.0.0.1:8000/"

# ====================== ComfyUISettings Class ======================
class ComfyUISettings:
    SETTINGS_DIR = "comfyui_presets"
    def __init__(self, data=None):
        if data:
            self.__dict__.update(data)
        else:
            self.presets_name = "默认"
            self.latent_width = 1216
            self.latent_height = 832
            self.batch_size = 1
            self.seed = "RANDOM"
            self.steps = 20
            self.cfg = 3.0
            self.checkpoint = "waiNSFWIllustrious_v120.safetensors"
            self.lora = ""
            self.prompt = "正面提示词"

    def save(self):
        os.makedirs("comfyui_presets", exist_ok=True)
        with open(f"comfyui_presets/{self.presets_name}.json", "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=4)

    @classmethod
    def load(cls, name):
        with open(f"comfyui_presets/{name}.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    @classmethod
    def list_presets(cls):
        if not os.path.exists("comfyui_presets"):
            return []
        return [f.replace(".json", "") for f in os.listdir("comfyui_presets") if f.endswith(".json")]

            
def api_system_stats(URL):
    try:
        response = requests.get(URL+"api/system_stats")

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        return None


def send_workflow(BASE_URL,comfyui_settings: ComfyUISettings,prompt: str):
    if comfyui_settings.lora == "" or comfyui_settings.lora == None:
        with open("workflows/base.json", "r",encoding="utf-8") as f:
            workflow_str = f.read()
    else:
        with open("workflows/base-lora.json", "r",encoding="utf-8") as f:
            workflow_str = f.read()

    workflow_str = workflow_str.replace("%CHECKPOINT%", comfyui_settings.checkpoint)
    workflow_str = workflow_str.replace("%LORA%", comfyui_settings.lora)

    workflow_str = workflow_str.replace("%PROMPT%", json.dumps(prompt)[1:-1])

    workflow_str = workflow_str.replace("%WIDTH%", str(comfyui_settings.latent_width))
    workflow_str = workflow_str.replace("%HEIGHT%", str(comfyui_settings.latent_height))
    workflow_str = workflow_str.replace("%BATCH_SIZE%", str(comfyui_settings.batch_size))

    if comfyui_settings.seed == "RANDOM" or comfyui_settings.seed == -1 or comfyui_settings.seed == "-1":
        workflow_str = workflow_str.replace("%SEED%", str(random.randint(0, 2**31 - 1)))
    else:
        workflow_str = workflow_str.replace("%SEED%", str(comfyui_settings.seed))
    workflow_str = workflow_str.replace("%STEPS%", str(comfyui_settings.steps))
    workflow_str = workflow_str.replace("%CFG%", str(comfyui_settings.cfg))


    workflow_json = json.loads(workflow_str)

    response = requests.post(BASE_URL+"prompt", json={"prompt": workflow_json})

    # Check for successful response and process results
    if response.status_code == 200:
        print("Workflow sent successfully!")

    else:
        print(f"Error: {response.status_code} - {response.text}")

def get_sample():
    pass

def get_loras():
    pass

def get_checkpoints():
    pass