from utilities.metadata import extract_metadata_properties, read_metadata_property, deserialize_metadata
from flask import Blueprint, Response, request, jsonify, stream_with_context
from contextlib import redirect_stdout, redirect_stderr
from huggingface_hub import hf_hub_download
from flask import current_app as app
from globals import components
import threading
import datetime
import select
import uuid
import os

models_blueprint = Blueprint('models', __name__)
running_model_instances = {}

@models_blueprint.route('/get/all', methods=['GET'])
def models_get_all():
    extensive = str(request.args.get('extensive', 'false')).lower() in ('true', '1', 'yes')
    include_data_keys = ["name", "description"]
    exclude_data_keys = ["identifier"]
    all_models_metadata = []
    extracted_metadata = {}

    try:
        for key, value in components.models.items():
            if extensive:
                extracted_metadata = extract_metadata_properties(value["data"], exclude_data_keys, "exclude", False)
            else:
                extracted_metadata = extract_metadata_properties(value["data"], include_data_keys, "include", True)

            if extracted_metadata is None:
                raise KeyError(f"Service '{key}' has no valid metadata") #TODO: better error message
        
            extracted_metadata = deserialize_metadata(extracted_metadata, 3 if extensive else 1)
            if extracted_metadata is None:
                raise KeyError(f"Service '{key}' has no valid metadata") #TODO: better error message
        
            all_models_metadata.append({key: extracted_metadata})
    except Exception as e:
        print(f"Failed to read available models metadata: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to read available models metadata: {str(e)}", "success": False}), 200
    
    return jsonify({"models": all_models_metadata, "success": True}), 200

@models_blueprint.route('/get/<model_id>', methods=['GET'])
def models_get_model(model_id):
    extensive = str(request.args.get('extensive', 'false')).lower() in ('true', '1', 'yes')
    include_data_keys = ["name", "description"]
    exclude_data_keys = ["identifier"]
    extracted_metadata = {}

    try:
        if not model_id:
            raise KeyError("Missing required parameters")
        
        if model_id not in components.models:
            raise KeyError(f"Model '{model_id}' not found")

        if extensive:
            extracted_metadata = extract_metadata_properties(components.models[model_id]["data"], exclude_data_keys, "exclude", False)
        else:
            extracted_metadata = extract_metadata_properties(components.models[model_id]["data"], include_data_keys, "include", True)

        if extracted_metadata is None:
            raise KeyError(f"Service '{model_id}' has no valid metadata") #TODO: better error message
            
        extracted_metadata = deserialize_metadata(extracted_metadata, 9 if extensive else 3)
        if extracted_metadata is None:
            raise KeyError(f"Service '{model_id}' has no valid metadata") #TODO: better error message
    except Exception as e:
        print(f"Failed to read model '{model_id}' metadata: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to read model '{model_id}' metadata: {str(e)}", "success": False}), 200

    return jsonify({"model": extracted_metadata, "success": True}), 200

@models_blueprint.route('/download/<model_id>', methods=['POST'])
def models_download_model(model_id):
    try:
        if not model_id:
            raise KeyError("Missing required parameters")

        if model_id not in components.models:
            raise KeyError(f"Model '{model_id}' not supported")

        repository = read_metadata_property(components.models[model_id], ["data", "repository"])
        filename = read_metadata_property(components.models[model_id], ["data", "filename"])
        base_directory = read_metadata_property(components.models[model_id], ["basedir"])

        instance_uuid = str(uuid.uuid4())
        os.makedirs(app.config["COMPONENTS_LOGS_DIRECTORY"], exist_ok=True)
        log_creation_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        download_log_file = f"{app.config["COMPONENTS_LOGS_DIRECTORY"]}/{log_creation_timestamp}_{model_id}_download_{instance_uuid}.log"
        # implement CivitAI downloader (at some point)
        # implement lora downloader (at some point)
        # TODO: the above!

        def model_download():
            try:
                with open(download_log_file, 'w') as log:
                    with redirect_stdout(log), redirect_stderr(log):
                        log.write(f"Starting download of {model_id} from {repository}")
                        hf_hub_download(repo_id=repository, filename=filename, local_dir=base_directory, repo_type="model")
                        log.write(f"Download of {model_id} from {repository} is complete!")
            except Exception as e:
                print(f"Error downloading model '{model_id}': {str(e)}")
        
        threading.Thread(target=model_download, daemon=True).start()
    except Exception as e:
        print(f"Failed to download model '{model_id}': {str(e)}")
        return jsonify({"error": f"Failed to download model '{model_id}': {str(e)}", "success": False}), 200
    
    return jsonify({"status": "Download started", "model_id": model_id}), 200

@models_blueprint.route('/stream/<model_id>/<command_id>/<instance_uuid>', methods=["GET"])
def services_stream_service_instance(model_id, command_id, instance_uuid):
    process: int = None

    try:
        if not model_id or not command_id:
            raise KeyError(f"Missing necessary parameters")

        if model_id not in components.models:
            raise KeyError(f"Model '{model_id}' not found")

        if command_id not in components.models[model_id]["data"]["commands"]:
            raise KeyError(f"Command '{command_id}' not found")

        if "instances" not in components.models[model_id]["data"]["commands"][command_id]:
            raise KeyError(f"No active instances of command '{command_id}' running")

        if instance_uuid not in components.models[model_id]["data"]["commands"][command_id]["instances"]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' not found")

        if "process" not in components.models[model_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' has no process associated with it")
        
        if "log_file" not in components.models[model_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' has no log file associated with it")

        log_file = components.models[model_id]["data"]["commands"][command_id]["instances"][instance_uuid]["log_file"]
        process = components.models[model_id]["data"]["commands"][command_id]["instances"][instance_uuid]["process"]

        if not log_file or not os.path.isfile(log_file):
            raise FileNotFoundError(f"Log file for instance '{instance_uuid}' not found")
    except Exception as e:
        print(f"Failed to stream service '{model_id}' instance: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to stream service '{model_id}' instance: {str(e)}", "success": False}), 200

    def stream_log_file():
        try:
            with open(log_file, "r") as f:
                # Move to the end if needed:
                # f.seek(0, os.SEEK_END)

                while True:
                    # Wait until data is ready to read, or timeout (non-blocking)
                    ready, _, _ = select.select([f], [], [], 0.25)
                    if ready:
                        line = f.readline()
                        if line:
                            yield line.rstrip("\n") + "\n"
                            continue

                    # Check if process has exited
                    try:
                        os.kill(process, 0)
                    except OSError:
                        break
        except GeneratorExit:
            # TODO: implement line tracking per user
            # client disconnected
            pass
        except Exception as e:
            print(f"Error while streaming log: {e}")
        finally:
            components.services[model_id]["data"]["commands"][command_id]["instances"].pop(instance_uuid, None)

    return Response(stream_with_context(stream_log_file()), mimetype='text/event-stream')
