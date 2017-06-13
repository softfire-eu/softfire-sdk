import concurrent
import logging
import socket
import time
import traceback
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor

import grpc

from sdk.softfire.grpc import messages_pb2_grpc, messages_pb2
from sdk.softfire.utils import get_config

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def _receive_forever(manager_instance):
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=int(manager_instance.get_config_value('system', 'server_threads', '5'))))
    messages_pb2_grpc.add_ManagerAgentServicer_to_server(_ManagerAgent(manager_instance), server)
    binding = '[::]:%s' % manager_instance.get_config_value('messaging', 'bind_port')
    logging.info("Start listening on %s" % binding)
    server.add_insecure_port(binding)
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        logging.warning("Got ctrl-c shutting down grpc")
        server.stop(0)


def _register(config_file_path):
    time.sleep(1)
    channel = grpc.insecure_channel(
        '%s:%s' % (get_config("system", "experiment_manager_ip", config_file_path),
                   get_config("system", "experiment_manager_port", config_file_path)))
    stub = messages_pb2_grpc.RegistrationServiceStub(channel)
    response = stub.register(
        messages_pb2.RegisterMessage(name=get_config("system", "name", config_file_path),
                                     endpoint="%s:%s" % (
                                         get_config("system", "ip", config_file_path),
                                         get_config("messaging", "bind_port", config_file_path)),
                                     description=get_config("system", "description", config_file_path)))
    logging.debug("Manager received registration response: %s" % response.result)


def _unregister(config_file_path):
    channel = grpc.insecure_channel(
        '%s:%s' % (get_config("system", "experiment_manager_ip", config_file_path),
                   get_config("system", "experiment_manager_port", config_file_path)))
    stub = messages_pb2_grpc.RegistrationServiceStub(channel)
    response = stub.unregister(
        messages_pb2.UnregisterMessage(name=get_config("system", "name", config_file_path),
                                       endpoint="%s:%s" % (
                                           get_config("system", "ip", config_file_path),
                                           get_config("messaging", "bind_port", config_file_path))))
    logging.debug("Manager received unregistration response: %s" % response.result)


class _ManagerAgent(messages_pb2_grpc.ManagerAgentServicer):
    def __init__(self, abstract_manager):
        """
        create the ManagerAgent in charge of dealing with the dispatch of messages
        :param abstract_manager: the Implementation of AbstractManager
         :type abstract_manager: AbstractManager
        """
        self.abstract_manager = abstract_manager

    def create_user(self, request, context):
        try:
            return self.abstract_manager.create_user(request)
        except Exception as e:
            return self.handle_error(e)

    def handle_error(self, e):
        if hasattr(e, "message"):
            return messages_pb2.ResponseMessage(result=messages_pb2.ERROR, error_message=e.message)
        if hasattr(e, "args"):
            return messages_pb2.ResponseMessage(result=messages_pb2.ERROR, error_message=e.args)
        return messages_pb2.ResponseMessage(result=messages_pb2.ERROR, error_message="No message available")

    def refresh_resources(self, request, context):
        try:
            resources = self.abstract_manager.refresh_resources(user_info=request)
            response = messages_pb2.ListResourceResponse(resources=resources)
            return messages_pb2.ResponseMessage(result=messages_pb2.Ok, list_resource=response)
        except Exception as e:
            return self.handle_error(e)

    def execute(self, request, context):
        if request.method == messages_pb2.LIST_RESOURCES:
            try:
                return messages_pb2.ResponseMessage(result=messages_pb2.Ok,
                                                    list_resource=messages_pb2.ListResourceResponse(
                                                        resources=self.abstract_manager.list_resources(
                                                            user_info=request.user_info,
                                                            payload=request.payload)))
            except Exception as e:
                return self.handle_error(e)
        if request.method == messages_pb2.PROVIDE_RESOURCES:
            try:
                return messages_pb2.ResponseMessage(result=messages_pb2.Ok,
                                                    provide_resource=messages_pb2.ProvideResourceResponse(
                                                        resources=[messages_pb2.Resource(content=r) for r in
                                                                   self.abstract_manager.provide_resources(
                                                                       user_info=request.user_info,
                                                                       payload=request.payload)]))
            except Exception as e:
                return self.handle_error(e)
        if request.method == messages_pb2.RELEASE_RESOURCES:
            try:
                self.abstract_manager.release_resources(user_info=request.user_info, payload=request.payload)
                return messages_pb2.ResponseMessage(result=messages_pb2.Ok)
            except Exception as e:
                return self.handle_error(e)

        if request.method == messages_pb2.VALIDATE_RESOURCES:
            try:
                self.abstract_manager.validate_resources(user_info=request.user_info, payload=request.payload)
                return messages_pb2.ResponseMessage(result=messages_pb2.Ok)
            except Exception as e:
                return self.handle_error(e)


def _is_ex_man__running(ex_man_bind_ip, ex_man_bind_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((ex_man_bind_ip, int(ex_man_bind_port)))
    sock.close()
    return result == 0


def start_manager(manager_instance):
    """
    Start the ExperimentManager
    :param config_file_path: path to the config file
    :param manager_instance: the instance of the Manager
    """
    logging.info("Starting %s Manager." % manager_instance.get_config_value('system', 'name'))

    if manager_instance.get_config_value("system", "wait_for_em", "true").lower() == "true":
        while not _is_ex_man__running(manager_instance.get_config_value("system", "experiment_manager_ip", "localhost"),
                                      manager_instance.get_config_value("system", "experiment_manager_port", "5051")):
            time.sleep(2)
    threads = []
    try:
        with ThreadPoolExecutor(2) as executor:
            threads.append(executor.submit(_receive_forever, manager_instance))
            threads.append(executor.submit(_register, manager_instance.config_file_path))
            cancel = False
            while True:
                for t in threads:
                    try:
                        if not cancel:
                            t.result(timeout=3)
                        else:
                            if t.running():
                                t.cancel()
                    except concurrent.futures.TimeoutError:
                        pass
                    except KeyboardInterrupt:
                        logging.warning("Got crtl-c inside...")
                        cancel = True

    except Exception:
        logging.warning("Got error...")
        traceback.print_exc()
    except KeyboardInterrupt:
        logging.warning("Got crtl-c...")
    finally:
        _unregister(manager_instance.config_file_path)


