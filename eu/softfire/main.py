import asyncio
import logging
import time
from concurrent import futures
from concurrent.futures import ProcessPoolExecutor
from random import randint

import grpc

from eu.softfire.grpc import messages_pb2_grpc, messages_pb2
from eu.softfire.utils import get_config

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def _receive_forever(manager_instance, config_file_path):
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=int(get_config('system', 'server_threads', config_file_path, '5'))))
    messages_pb2_grpc.add_ManagerAgentServicer_to_server(_ManagerAgent(manager_instance), server)
    binding = '[::]:%s' % get_config('messaging', 'bind_port', config_file_path, randint(1025, 65535))
    logging.info("Start listening on %s" % binding)
    server.add_insecure_port(binding)
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


def _register(config_file_path):
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
        return self.abstract_manager.create_user(request.name, request.password)

    def refresh_resources(self, request, context):
        try:
            return messages_pb2.ResponseMessage(result=0,
                                                list_resource=self.abstract_manager.refresh_resources(
                                                    user_info=request)
                                                )
        except Exception as e:
            if hasattr(e, "message"):
                return messages_pb2.ResponseMessage(result=2, error_message=e.message)
            if hasattr(e, "args"):
                return messages_pb2.ResponseMessage(result=2, error_message=e.args)
            return messages_pb2.ResponseMessage(result=2, error_message="No message available")

    def execute(self, request, context):
        if request.method == messages_pb2.LIST_RESOURCES:
            try:
                return messages_pb2.ResponseMessage(result=0,
                                                    list_resource=messages_pb2.ListResourceResponse(
                                                        resources=self.abstract_manager.list_resources(
                                                            user_info=request.user_info,
                                                            payload=request.payload)))
            except Exception as e:
                return messages_pb2.ResponseMessage(result=2, error_message=e)
        if request.method == messages_pb2.PROVIDE_RESOURCES:
            try:
                return messages_pb2.ResponseMessage(result=0,
                                                    provide_resource=messages_pb2.ProvideResourceResponse(
                                                        resources=[messages_pb2.Resource(content=r) for r in
                                                                   self.abstract_manager.provide_resources(
                                                                       user_info=request.user_info,
                                                                       payload=request.payload)]))
            except Exception as e:
                return messages_pb2.ResponseMessage(result=2, error_message=e)
        if request.method == messages_pb2.RELEASE_RESOURCES:
            try:
                self.abstract_manager.release_resources(user_info=request.user_info, payload=request.payload)
                return messages_pb2.ResponseMessage(result=0)
            except Exception as e:
                return messages_pb2.ResponseMessage(result=2, error_message=e)


def start_manager(manager_instance, config_file_path):
    """
    Start the ExperimentManager
    :param config_file_path: path to the config file
    :param manager_instance: the instance of the Manager
    """
    logging.info("Starting %s Manager." % get_config('system', 'name', config_file_path, ''))

    executor = ProcessPoolExecutor(5)
    loop = asyncio.get_event_loop()

    asyncio.ensure_future(loop.run_in_executor(executor, _receive_forever, manager_instance, config_file_path))
    asyncio.ensure_future(loop.run_in_executor(executor, _register, config_file_path))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info("received ctrl-c, shutting down...")
        loop.close()
        _unregister(config_file_path)
