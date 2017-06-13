import logging
import socket
import sys
import threading
import time
from concurrent import futures
from threading import Thread

import grpc

from sdk.softfire.grpc import messages_pb2_grpc, messages_pb2
from sdk.softfire.utils import get_config

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def _receive_forever(manager_instance, event: threading.Event):
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=int(manager_instance.get_config_value('system', 'server_threads', '5'))))
    messages_pb2_grpc.add_ManagerAgentServicer_to_server(_ManagerAgent(manager_instance), server)
    binding = '[::]:%s' % manager_instance.get_config_value('messaging', 'bind_port')
    logging.info("Start listening on %s" % binding)
    server.add_insecure_port(binding)
    server.start()
    while event.wait(_ONE_DAY_IN_SECONDS):
        logging.info("Shutting down gRPC")
        server.stop(0)
        return


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

    event = threading.Event()
    listen_thread = ExceptionHandlerThread(target=_receive_forever, args=[manager_instance, event])
    register_thread = ExceptionHandlerThread(target=_register, args=[manager_instance.config_file_path])

    listen_thread.start()
    register_thread.start()

    while True:
        try:
            time.sleep(30)
        except InterruptedError:
            _going_down(event, listen_thread, register_thread)
        except KeyboardInterrupt:
            _going_down(event, listen_thread, register_thread)
        finally:
            _unregister(manager_instance.config_file_path)
            return

def _going_down(event, listen_thread, register_thread):
    if listen_thread.is_alive():
        event.set()
        listen_thread.join(timeout=5)
    if register_thread.is_alive():
        register_thread.join(timeout=3)


class ExceptionHandlerThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        if sys.version_info > (3, 0):
            super().__init__(group, target, name, args, kwargs, daemon=daemon)
        else:
            super(self.__class__, self).__init__(group, target, name, args, kwargs, daemon=daemon)
        self.exception = None

    def run(self):
        try:
            if sys.version_info > (3, 0):
                super().run()
            else:
                super(self.__class__, self).run()
        except Exception as e:
            self.exception = e
