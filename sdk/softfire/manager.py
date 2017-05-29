from abc import ABCMeta, abstractmethod

from sdk.softfire.grpc.messages_pb2 import UserInfo


class AbstractManager(metaclass=ABCMeta):
    @abstractmethod
    def list_resources(self, user_info=None, payload=None) -> list:
        """
        List all available resources
        
        :param payload: 
        :return: a list of messages_pb2.ResourceMetadata
        """
        pass

    @abstractmethod
    def validate_resources(self, user_info=None, payload=None) -> None:
        """
        Validate the resources

        :param payload: 
        :raise any exception for error
        """
        pass

    @abstractmethod
    def provide_resources(self, user_info, payload=None) -> list:
        """
        Deploy the specific resources
        Must return a list of JSON string representing the deployed resources
         
        :param payload: string representing the request
         :type payload: str
        :return: a list of JSON string representing the deployed resources
         :rtype: list
        """
        pass

    @abstractmethod
    def release_resources(self, user_info, payload=None) -> None:
        """
        Release resources of that user
        :param payload: 
        :return: 
        """
        pass

    @abstractmethod
    def create_user(self, username, password):
        """
        Create user
        :param username: the username 
        :param password: the password
        :return: UserInfo updated
         :rtype UserInfo
        """
        pass

    @abstractmethod
    def refresh_resources(self, user_info) -> list:
        """
        refresh the list of resources. Same as list resources
        :param user_info: the User requesting
        :return: list of ResourceMetadata
        """
        pass
