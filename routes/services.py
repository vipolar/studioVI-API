from utilities.metadata import extract_metadata_properties, deserialize_metadata
from flask import Blueprint, Response, request, jsonify, stream_with_context
from utilities.authutilities import authentication_required
from flask import current_app as app
from globals import components
from string import Template
import subprocess
import threading
import datetime
import logging
import select
import psutil
import shlex
import uuid
import os
import re

from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request


UUID4_REGEX = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89abAB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}$")
services_blueprint = Blueprint('services', __name__)
running_service_instances = {}

@services_blueprint.route('/get/all', methods=['GET'])
def services_get_all():
    extensive = str(request.args.get('extensive', 'false')).lower() in ('true', '1', 'yes')
    include_data_keys = ["name", "description"]
    exclude_data_keys = ["identifier"]
    all_services_metadata = []
    extracted_metadata = {}

    try:
        for key, value in components.services.items():
            if extensive:
                extracted_metadata = extract_metadata_properties(value["data"], exclude_data_keys, "exclude", False)
            else:
                extracted_metadata = extract_metadata_properties(value["data"], include_data_keys, "include", True)

            if extracted_metadata is None:
                raise KeyError(f"Service '{key}' has no valid metadata") #TODO: better error message

            extracted_metadata = deserialize_metadata(extracted_metadata, 3 if extensive else 1)
            if extracted_metadata is None:
                raise KeyError(f"Service '{key}' has no valid metadata") #TODO: better error message

            all_services_metadata.append({key: extracted_metadata})
    except Exception as e:
        print(f"Failed to read available services metadata: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to read available services metadata: {str(e)}", "success": False}), 200
    
    return jsonify(all_services_metadata), 200

@services_blueprint.route('/get/<service_id>', methods=['GET'])
def services_get_service(service_id):
    extensive = str(request.args.get('extensive', 'false')).lower() in ('true', '1', 'yes')
    include_data_keys = ["name", "description"]
    exclude_data_keys = ["identifier"]
    extracted_metadata = {}
    installed = []

    try:
        if not service_id:
            raise KeyError("Missing required parameters")
        
        if service_id not in components.services:
            raise KeyError(f"Service '{service_id}' not found")

        if "installed" in components.services[service_id]["data"]:
            instances = os.listdir(components.services[service_id]["basedir"])
            if instances:
                for instance in instances: #TODO: do this from db and not from filesystem
                    if not os.path.isdir(components.services[service_id]["basedir"] + f"/{instance}"):
                        continue
                    if not UUID4_REGEX.match(instance):
                        continue
                    installed.append(instance)

        if extensive:
            extracted_metadata = extract_metadata_properties(components.services[service_id]["data"], exclude_data_keys, "exclude", False)
        else:
            extracted_metadata = extract_metadata_properties(components.services[service_id]["data"], include_data_keys, "include", True)
        
        if extracted_metadata is None:
            raise KeyError(f"Service '{service_id}' has no valid metadata") #TODO: better error message
            
        extracted_metadata = deserialize_metadata(extracted_metadata, 9 if extensive else 3)
        if extracted_metadata is None:
            raise KeyError(f"Service '{service_id}' has no valid metadata") #TODO: better error message

        if "installed" in extracted_metadata:
            extracted_metadata["installed"] = installed
    except Exception as e:
        print(f"Failed to read service '{service_id}' metadata: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to read service '{service_id}' metadata: {str(e)}", "success": False}), 200

    logging.debug(f"Service '{service_id}' metadata: {extracted_metadata}")  # DEBUG
    return jsonify({"service": extracted_metadata, "success": True}), 200

@services_blueprint.route('/launch/<service_id>/<command_id>', methods=["POST"])
#@authentication_required() #mock the auth and user for now
def services_launch_service(service_id, command_id):
    instance_uuid = None
    environment = None
    installed = None
    process = None
    cli = None

    try:
        if not service_id or not command_id:
            raise KeyError(f"Missing necessary parameters")

        if service_id not in components.services:
            raise KeyError(f"Service '{service_id}' not supported")

        if command_id not in components.services[service_id]["data"]["commands"]:
            raise KeyError(f"Command '{command_id}' is not a valid command")

        if "launcher" not in components.services[service_id]["data"]["commands"][command_id]:
            raise KeyError(f"Command '{command_id}' has no valid launcher")

        if "instance" in components.services[service_id]["data"]["commands"][command_id]:
            installed = request.args.get('instance', "None")
            if not installed:
                raise KeyError(f"Command '{command_id}' requires an installed instance to be specified")
            # TODO: do permission checks here (when actually have users)
        
        for service_key, service_value in components.services.items():
            if service_key != service_id and "data" in service_value and "commands" in service_value["data"]:
                for command_key, command_value in service_value["data"]["commands"].items():
                    if "instances" in command_value and len(command_value["instances"]) > 1 and "blockOtherServices" in command_value:
                        if isinstance(command_value["blockOtherServices"], list) and service_id in command_value["blockOtherServices"]:
                            raise KeyError(f"Currently running service '{service_key}' command '{command_key}' is explicitely blocking service '{service_id}' from executing")
                        elif isinstance(command_value["blockOtherServices"], dict) and  service_id in command_value["blockOtherServices"]:
                            if isinstance(command_value["blockOtherServices"][service_id], list) and command_id in command_value["blockOtherServices"][service_id]:
                                raise KeyError(f"Currently running service '{service_key}' command '{command_key}' is explicitely blocking service '{service_id}' command '{command_id}' from executing")
                            elif isinstance(command_value["blockOtherServices"][service_id], dict) and command_id in command_value["blockOtherServices"][service_id]:
                                raise KeyError(f"Currently running service '{service_key}' command '{command_key}' is explicitely blocking service '{service_id}' command '{command_id}' from executing")
                            elif isinstance(command_value["blockOtherServices"][service_id], str) and command_id == command_value["blockOtherServices"][service_id]:
                                raise KeyError(f"Currently running service '{service_key}' command '{command_key}' is explicitely blocking service '{service_id}' command '{command_id}' from executing")
                            elif isinstance(command_value["blockOtherServices"][service_id], bool) and command_value["blockOtherServices"][service_id] is True:
                                raise KeyError(f"Currently running service '{service_key}' command '{command_key}' is explicitely blocking service '{service_id}' from executing")
                        elif isinstance(command_value["blockOtherServices"], str) and service_id == command_value["blockOtherServices"]:
                            raise KeyError(f"Currently running service '{service_key}' command '{command_key}' is explicitely blocking service '{service_id}' from executing")
                        elif isinstance(command_value["blockOtherServices"], bool) and command_value["blockOtherServices"] is True:
                            raise KeyError(f"Currently running service '{service_key}' command '{command_key}' is blocking service '{service_id}' from executing")

        for command_key, command_value in components.services[service_id]["data"]["commands"].items():
            if command_key != command_id and "instances" in command_value and len(command_value["instances"]) > 1 and "blockOtherCommands" in command_value:
                if isinstance(command_value["blockOtherCommands"], bool) and command_value["blockOtherCommands"] is True:
                    raise KeyError(f"Currently running command '{command_key}' is blocking command '{command_id}' from executing")
                elif isinstance(command_value["blockOtherCommands"], list) and command_id in command_value["blockOtherCommands"]:
                    raise KeyError(f"Currently running command '{command_key}' is explicitely blocking command '{command_id}' from executing")
                elif isinstance(command_value["blockOtherCommands"], str) and command_id ==  command_value["blockOtherCommands"]:
                    raise KeyError(f"Currently running command '{command_key}' is explicitely blocking command '{command_id}' from executing")

        if "instances" in components.services[service_id]["data"]["commands"][command_id]:
            if len(components.services[service_id]["data"]["commands"][command_id]["instances"]) > 1:
                if "allowMultipleInstances" not in components.services[service_id]["data"]["commands"][command_id] or components.services[service_id]["data"]["commands"][command_id]["allowMultipleInstances"] is False:
                    raise KeyError(f"Command '{command_id}' does not support multiple instances and there is an existing instance running already")
        else:
            components.services[service_id]["data"]["commands"][command_id]["instances"] = {"deserializationThreshold": 9}

        cli = components.services[service_id]["data"]["commands"][command_id]["launcher"]
        if "cliArguments" in components.services[service_id]["data"]["commands"][command_id]:
            cli_args = components.services[service_id]["data"]["commands"][command_id]["cliArguments"]
            cli_args_list = []
            if not isinstance(cli_args, dict):
                raise KeyError(f"Command '{command_id}' has invalid CLI arguments format")
            for key, value in cli_args.items():
                if not isinstance(key, str):
                    raise KeyError(f"Command '{command_id}' has invalid CLI argument: {key}")
                cli_args_list.append(key)
                if value:
                    cli_args_list.append(str(value))
            cli = cli + " " + " ".join(cli_args_list)

        if "envVariables" in components.services[service_id]["data"]["commands"][command_id]:
            env = components.services[service_id]["data"]["commands"][command_id]["envVariables"]
            if not isinstance(env, dict):
                raise KeyError(f"Command '{command_id}' has invalid environment variables format")
            for key, value in env.items():
                if not isinstance(key, str):
                    raise KeyError(f"Command '{command_id}' has invalid environment variable: {key}")
            environment = os.environ.copy()
            environment.update(env)

        template = Template(cli)
        instance_uuid = str(uuid.uuid4())
        template_identifiers = template.get_identifiers()
        request_cli_args = request.args.get('cliArguments', {})
        if not isinstance(request_cli_args, dict):
            raise KeyError(f"Invalid CLI arguments format for command: {command_id}")
        request_cli_args['instance_uuid'] = instance_uuid

        template_substitutions = {}
        for identifier in template_identifiers:
            if identifier not in request_cli_args:
                raise KeyError(f"Command '{command_id}' has missing CLI argument: {identifier}")
            template_substitutions[identifier] = request_cli_args[identifier]
        cli = template.substitute(template_substitutions)

        
        os.makedirs(app.config["COMPONENTS_LOGS_DIRECTORY"], exist_ok=True)
        log_creation_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        instance_log_file = f"{app.config["COMPONENTS_LOGS_DIRECTORY"]}/{log_creation_timestamp}_{service_id}_{command_id}_{instance_uuid}.log"
        working_directory = components.services[service_id]["basedir"] + f"/{installed}" if installed else ""
        process_log_file = open(instance_log_file, "w")
        shell_ready_command = shlex.split(cli)
        process = subprocess.Popen(
            shell_ready_command,
            cwd=working_directory,
            stdout=process_log_file,
            stderr=subprocess.STDOUT,
            text=True, user=None,
            env=environment,
        )

        ps_process = psutil.Process(process.pid)
        create_time = ps_process.create_time()
        instance = {
            "deserializationThreshold": 99,
            "log_file": instance_log_file,
            "create_time": create_time,
            "process": process.pid,
            "user": "user"
        }

        def _exit_process():
            try:
                process.wait()
            except Exception as e:
                print(f"{instance_uuid}: {e}")
                process_log_file.write(f"\n{e}\n")
            finally:
                process_log_file.write(f"\nProcess '{process.pid}' spawned by '{instance_uuid}' instance has exited with return code: {process.returncode}\n")
                components.services[service_id]["data"]["commands"][command_id]["instances"].pop(instance_uuid, None)
                process_log_file.close()

        threading.Thread(target=_exit_process, daemon=True).start()
        components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid] = instance
    except Exception as e:
        print(f"Service '{service_id}' cannot be launched: {str(e)}") #DEBUG
        return jsonify({"error": f"Service '{service_id}' cannot be launched: {str(e)}", "success": False}), 200

    return jsonify({"instance": instance_uuid, "success": True}), 200

@services_blueprint.route('/get/<service_id>/<command_id>/instances', methods=["GET"])
def services_get_service_instances(service_id, command_id):
    service_instances = []

    try:
        if not service_id or not command_id:
            raise KeyError(f"Missing necessary parameters")

        if service_id not in components.services:
            raise KeyError(f"Service '{service_id}' not found")

        if command_id not in components.services[service_id]["data"]["commands"]:
            raise KeyError(f"Command '{command_id}' not found")

        if "instances" not in components.services[service_id]["data"]["commands"][command_id]:
            raise KeyError(f"No active instances of command '{command_id}' running")

        service_instances = [
            key for key in components.services[service_id]["data"]["commands"][command_id]["instances"].keys()
            if key != "deserializationThreshold"
        ]
    except Exception as e:
        print(f"Failed to look up service '{service_id}' instances: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to look up service '{service_id}' instances: {str(e)}", "success": False}), 200

    return jsonify({"instances": service_instances, "success": True}), 200

@services_blueprint.route('/stream/<service_id>/<command_id>/<instance_uuid>', methods=["GET"])
def services_stream_service_instance(service_id, command_id, instance_uuid):
    process: int = None

    try:
        if not service_id or not command_id:
            raise KeyError(f"Missing necessary parameters")

        if service_id not in components.services:
            raise KeyError(f"Service '{service_id}' not found")

        if command_id not in components.services[service_id]["data"]["commands"]:
            raise KeyError(f"Command '{command_id}' not found")

        if "instances" not in components.services[service_id]["data"]["commands"][command_id]:
            raise KeyError(f"No active instances of command '{command_id}' running")

        if instance_uuid not in components.services[service_id]["data"]["commands"][command_id]["instances"]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' not found")

        if "process" not in components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' has no process associated with it")
        
        if "log_file" not in components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' has no log file associated with it")

        log_file = components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]["log_file"]
        process = components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]["process"]

        if not log_file or not os.path.isfile(log_file):
            raise FileNotFoundError(f"Log file for instance '{instance_uuid}' not found")
    except Exception as e:
        print(f"Failed to stream service '{service_id}' instance: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to stream service '{service_id}' instance: {str(e)}", "success": False}), 200

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
            components.services[service_id]["data"]["commands"][command_id]["instances"].pop(instance_uuid, None)

    return Response(stream_with_context(stream_log_file()), mimetype='text/event-stream')

@services_blueprint.route("/interrupt/<service_id>/<command_id>/<instance_uuid>", methods=["DELETE"])
def services_interrupt_service_instance(service_id, command_id, instance_uuid):
    try:
        if not service_id or not command_id:
            raise KeyError(f"Missing necessary parameters")

        if service_id not in components.services:
            raise KeyError(f"Service '{service_id}' not found")

        if command_id not in components.services[service_id]["data"]["commands"]:
            raise KeyError(f"Command '{command_id}' not found")

        if "instances" not in components.services[service_id]["data"]["commands"][command_id]:
            raise KeyError(f"No active instances of command '{command_id}' running")

        if instance_uuid not in components.services[service_id]["data"]["commands"][command_id]["instances"]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' not found")

        if "process" not in components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' has no process associated with it")

        if "create_time" not in components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' has no start time associated with it")
        
        if "termination_log_file" in components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' is already exiting")

        if "log_file" not in components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]:
            raise KeyError(f"Command '{command_id}' instance '{instance_uuid}' has no log file associated with it")

        create_time = components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]["create_time"]
        log_file = components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]["log_file"]
        pid = components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]["process"]
        timeout = int(request.args.get('timeout', app.config["PROCESS_GRACEFUL_SHUTDOWN_TIMEOUT"]))
        kill = str(request.args.get('kill', 'false')).lower() in ('true', '1', 'yes')

        if timeout < 0:
            raise ValueError("Timeout must be a non-negative integer")
        base, ext = os.path.splitext(log_file)
        termination_log_file = f"{base}_termination{ext}"

        def _terminate():
            try:
                with open(termination_log_file, "w") as log:
                    os.kill(pid, 0)
                    process = psutil.Process(pid)
                    if process.create_time() != create_time:
                        raise psutil.NoSuchProcess(f"Process '{process}' does not match the expected creation time")
                    processes = process.children(recursive=True)
                    processes.append(process)

                    if processes and not kill:
                        terminated = []
                        for process in processes:
                            try:
                                process.terminate()
                                log.write(f"Sent terminate signal to process '{process.pid}' spawned by '{instance_uuid}' instance\n")
                            except psutil.NoSuchProcess:
                                log.write(f"Process {process.pid} spawned by '{instance_uuid}' instance has already terminated\n")
                                terminated.append(process)
                                pass

                        for process in terminated:
                            processes.remove(process)

                        try:
                            gone, alive = psutil.wait_procs(processes, timeout=timeout)

                            if gone:
                                for process in gone:
                                    log.write(f"Process {process.pid} spawned by '{instance_uuid}' instance has exited with a '{process.returncode}' return code\n")
                                    if process in processes:
                                        processes.remove(process)
                        except Exception:
                            log.write(f"Failed to wait for processes spawned by '{instance_uuid}' instance to shutdown gracefully\n")

                    if processes:
                        terminated = []
                        log.write(f"Sending kill signal to processes spawned by '{instance_uuid}' instance\n")
                        for process in processes:
                            try:
                                process.kill()
                                log.write(f"Sent kill signal to process '{process.pid}' spawned by '{instance_uuid}' instance\n")
                            except psutil.NoSuchProcess:
                                log.write(f"Process {process.pid} spawned by '{instance_uuid}' instance has already terminated\n")
                                terminated.append(process)
                                pass

                        for process in terminated:
                            processes.remove(process)

                    try:
                        psutil.wait_procs(processes, timeout=timeout // 2 if timeout > 0 else None)
                    except Exception:
                        log.write(f"Failed to wait for processes spawned by '{instance_uuid}' instance to be killed\n")
                        pass  # Ignore further wait errors
            except psutil.NoSuchProcess:
                log.write(f"Process {pid} spawned by '{instance_uuid}' instance has already terminated\n")
            except Exception as e:
                log.write(f"Instance '{instance_uuid}' couldn't be terminated: {str(e)}\n")

        components.services[service_id]["data"]["commands"][command_id]["instances"][instance_uuid]["termination_log_file"] = termination_log_file
        threading.Thread(target=_terminate, daemon=True).start()
    except Exception as e:
        print(f"Failed to terminate service '{service_id}' instance: {str(e)}") #DEBUG
        return jsonify({"error": f"Failed to terminate service '{service_id}' instance: {str(e)}", "success": False}), 500

    return jsonify({"message": f"Termination process for instance '{instance_uuid}' has started", "success": True}), 200
