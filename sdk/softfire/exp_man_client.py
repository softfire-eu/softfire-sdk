import json
import logging
import os
import traceback

import requests

from sdk.softfire.utils import ExperimentManagerClientError


class ExpManClient(object):
    def __init__(self, username, password, experiment_manager_ip, experiment_manager_port, debug=False):

        self.log = logging.getLogger(__name__)
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        self.experiment_manager_login_url = 'http://{}:{}/login'.format(experiment_manager_ip, experiment_manager_port)
        self.experiment_manager_create_user_url = 'http://{}:{}/create_user'.format(experiment_manager_ip,
                                                                                    experiment_manager_port)
        self.experiment_manager_delete_user_url = 'http://{}:{}/delete_user'.format(experiment_manager_ip,
                                                                                    experiment_manager_port)
        self.experiment_manager_upload_experiment_url = 'http://{}:{}/reserve_resources'.format(experiment_manager_ip,
                                                                                                experiment_manager_port)
        self.experiment_manager_deploy_experiment_url = 'http://{}:{}/provide_resources'.format(experiment_manager_ip,
                                                                                                experiment_manager_port)
        self.experiment_manager_delete_experiment_url = 'http://{}:{}/release_resources'.format(experiment_manager_ip,
                                                                                                experiment_manager_port)
        self.experiment_manager_get_status_url = 'http://{}:{}/get_status'.format(experiment_manager_ip,
                                                                                  experiment_manager_port)
        self.experiment_manager_get_resources_url = 'http://{}:{}/get_resources'.format(experiment_manager_ip,
                                                                                        experiment_manager_port)
        self.experiment_manager_get_experimenters_url = 'http://{}:{}/experimenters'.format(experiment_manager_ip,
                                                                                            experiment_manager_port)
        self.experiment_manager_create_certificate_url = 'http://{}:{}/certificates'.format(experiment_manager_ip,
                                                                                            experiment_manager_port)
        self.experiment_manager_check_user_url = 'http://{}:{}/check_user'.format(experiment_manager_ip,
                                                                                  experiment_manager_port)
        self.session = self._log_in(username=username, password=password)

    def _log_in(self, username, password):
        """
        Returns a Session object from the requests module on which the user has logged into the experiment manager.
        :param username:
        :param password:
        :return:
        """
        self.log.debug('Try to log into the experiment-manager as user \'{}\'.'.format(username))
        session = requests.Session()
        try:
            log_in_response = session.post(self.experiment_manager_login_url,
                                           data={'username': username, 'password': password})
            self.__validate_response_status(log_in_response, [200],
                                            'experiment-manager log in failed for user {}. HTTP response status code '
                                            'was {}, but expected was {}.'.format(
                                                username, log_in_response, [200]))
            response_text_dict = json.loads(log_in_response.text)
        except ConnectionError as ce:
            error_message = 'Could not connect to the experiment-manager for logging in.'
            self.log.error(error_message)
            traceback.print_exc()
            raise Exception(error_message)
        except Exception as e:
            error_message = 'Exception while logging into the experiment manager.'
            self.log.error(error_message)
            traceback.print_exc()
            raise Exception(error_message)
        if (not response_text_dict.get('ok')) or response_text_dict.get('ok') == False:
            error_message = 'experiment-manager log in failed: {}'.format(response_text_dict.get('msg'))
            self.log.error(error_message)
            raise Exception(error_message)
        self.log.debug('Log in succeeded for user {}.'.format(username))
        return session

    def __validate_response_status(self, response, expected_status, error_message=None):
        if not isinstance(expected_status, list):
            expected_status = [expected_status]

        if response.status_code not in expected_status:
            content = response.content
            try:
                content = content.decode('UTF-8')
            except:
                pass
            error_message = 'HTTP response status code was {}, but expected was {}'.format(response.status_code,
                                                                                           expected_status) or error_message
            self.log.error('HTTP response status code was {}, but expected was {}: {}'.format(response.status_code,
                                                                                              expected_status, content))
            raise Exception(error_message)

    def create_user(self, new_user_name, new_user_pwd, new_user_role, wait_for=False, timeout=600):
        self.log.debug('Try to create a new user named \'{}\'.'.format(new_user_name))
        response = self.session.post(self.experiment_manager_create_user_url,
                                     data={'username': new_user_name, 'password': new_user_pwd, 'role': new_user_role})
        self.__validate_response_status(response, [200, 202])
        self.log.debug('Triggered the creation of a new user named \'{}\'.'.format(new_user_name))
        if wait_for:
            for x in range(0, timeout, 5):
                self.check_user(new_user_name)

    def delete_user(self, user_name_to_delete):
        self.log.debug('Try to delete the user named \'{}\'.'.format(user_name_to_delete))
        response = self.session.post(self.experiment_manager_delete_user_url,
                                     data={'username': user_name_to_delete})
        self.__validate_response_status(response, 200)
        self.log.debug('Deletion of user \'{}\' succeeded.'.format(user_name_to_delete))

    def upload_experiment(self, experiment_file_path):
        self.log.debug('Try to upload experiment.')
        if not os.path.isfile(experiment_file_path):
            raise FileNotFoundError('Experiment file {} not found'.format(experiment_file_path))
        with open(experiment_file_path, 'rb') as experiment_file:
            response = self.session.post(self.experiment_manager_upload_experiment_url, files={'data': experiment_file})
            self.__validate_response_status(response, 200)
        self.log.debug('Upload of experiment succeeded.')

    def deploy_experiment(self, queue=None):
        try:
            self.log.debug('Try to deploy experiment.')
            response = self.session.post(self.experiment_manager_deploy_experiment_url)
            self.__validate_response_status(response, 200)
            self.log.debug('Deployment of experiment succeeded.')
            if queue is not None:
                queue.put(None)
        except Exception as e:
            if queue is not None:
                traceback.print_exc()
                queue.put(e)
            else:
                raise e

    def delete_experiment(self):
        self.log.debug('Try to remove experiment.')
        response = self.session.post(self.experiment_manager_delete_experiment_url)
        self.__validate_response_status(response, 200)
        self.log.debug('Removal of experiment succeeded.')

    def get_experiment_status(self):
        self.log.debug('Try to get the experiement\'s status.')
        response = self.session.get(self.experiment_manager_get_status_url)
        self.__validate_response_status(response, 200)
        return json.loads(response.text)

    def get_resource_from_id(self, used_resource_id):
        resources = self.get_experiment_status()
        for res in resources:
            if res.get('used_resource_id') == used_resource_id:
                return res.get('value').strip("'")
        raise ExperimentManagerClientError("Resource with id %s not found" % used_resource_id)

    def get_all_resources(self):
        response = self.session.get(self.experiment_manager_get_resources_url)
        self.__validate_response_status(response, 200)
        return json.loads(response.text)

    def get_all_experimenters(self):
        response = self.session.get(self.experiment_manager_get_experimenters_url)
        self.__validate_response_status(response, 200)
        return json.loads(response.text)

    def create_certificate(self, username, password, days):
        response = self.session.post(self.experiment_manager_create_certificate_url,
                                     data={'username': username, 'password': password, 'days': days})
        self.__validate_response_status(response, 200)
        return response.text

    def check_user(self, new_user_name):
        return self.session.post(self.experiment_manager_check_user_url,
                                 data={'username': new_user_name}).status_code == 200
