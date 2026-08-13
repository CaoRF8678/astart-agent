import os


def read_config():
    """Read the deploy_starter/config.yml file using the original simple parser."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yml")
    config = {}
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    config[key] = value
    return config


config = read_config()
