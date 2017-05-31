from abc import ABCMeta, abstractmethod

from sdk.softfire.utils import get_config


class AbstractManager(metaclass=ABCMeta):
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path

    def get_config_value(self, section, key, default=None):
        return get_config(section=section, key=key, default=default, config_file_path=self.config_file_path)

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

    def update_status(self) -> list:
        """
        update the status of the experiments in case of value change

        :return: list of json strings representing the value of the resources changed
        """
        pass
