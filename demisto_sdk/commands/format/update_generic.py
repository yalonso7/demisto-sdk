from typing import Union, List, Tuple
from demisto_sdk.commands.common.hook_validations.structure import StructureValidator
from demisto_sdk.commands.common.tools import print_color, LOG_COLORS, get_dict_from_file, get_remote_file, is_file_from_content_repo
import os
import yaml
from ruamel.yaml import YAML
from demisto_sdk.commands.common.constants import NEW_FILE_DEFAULT_FROMVERSION, OLD_FILE_DEFAULT_FROMVERSION
ryaml = YAML()
ryaml.allow_duplicate_keys = True


class BaseUpdate:
    """BaseUpdate is the base class for all format commands.
        Attributes:
            source_file (str): the path to the file we are updating at the moment.
            output_file (str): the desired file name to save the updated version of the YML to.
            relative_content_path (str): Relative content path of output path.
            old_file (bool): Whether the file is a added file = new or a modified file = old.
            old_file_data (dict): Data of old file from content repo, if exist.
            schema_path (str): Schema path of file.
            from_version (str): Value of Wanted fromVersion key in file.
            data (dict): Dictionary of loaded file.
            file_type (str): Whether the file is yml or json.
            arguments_to_remove (list): List of keys in file that should be removed.
            from_version_key (str): The fromVersion key in file, different between yml and json files.
    """

    def __init__(self, input: str = '', output: str = '', path: str = '', from_version: str = ''):
        self.source_file = input
        self.output_file = self.set_output_file_path(output)
        _, self.relative_content_path = is_file_from_content_repo(self.output_file)
        self.old_file_data, self.old_file = self.is_old_file(self.relative_content_path if self.relative_content_path else self.output_file)
        self.schema_path = path
        self.from_version = from_version

        if not self.source_file:
            raise Exception('Please provide <source path>, <optional - destination path>.')
        try:
            self.data, self.file_type = get_dict_from_file(self.source_file)
        except Exception:
            raise Exception(F'Provided file {self.source_file} is not a valid file.')
        self.arguments_to_remove = self.arguments_to_remove()
        self.from_version_key = self.set_from_version_key_name()

    def set_output_file_path(self, output_file_path) -> str:
        """Creates and format the output file name according to user input.
        Args:
            output_file_path: The output file name the user defined.
        Returns:
            str. the full formatted output file name.
        """
        if not output_file_path:
            source_dir = os.path.dirname(self.source_file)
            file_name = os.path.basename(self.source_file)
            if self.__class__.__name__ == 'PlaybookYMLFormat':
                if "Pack" not in source_dir:
                    if not file_name.startswith('playbook-'):
                        file_name = F'playbook-{file_name}'

            return os.path.join(source_dir, file_name)
        else:
            return output_file_path

    def remove_unnecessary_keys(self):
        """Removes keys that are in file but not in schema of file type"""
        for key in self.arguments_to_remove:
            print(F'Removing Unnecessary fields {key} from file')
            self.data.pop(key, None)

    def set_fromVersion(self, from_version=None):
        """Sets fromversion key in file:
        Args:
            from_version: The specific from_version value.
        """
        # if output path is in content repo already than check fromversion in it, otherwise check current file
        if not self.old_file:
            print(F'Setting fromVersion field')
            if self.from_version_key not in self.data:
                if from_version:
                    self.data[self.from_version_key] = from_version
                else:
                    self.data[self.from_version_key] = NEW_FILE_DEFAULT_FROMVERSION

        # for modified files, set prefered fromVersion field, givven or default
        else:
            if self.from_version_key not in self.data:
                if from_version:
                    self.data[self.from_version_key] = from_version
                elif self.from_version_key in self.old_file_data:
                    self.data[self.from_version_key] = self.old_file_data[self.from_version_key]
                else:
                    self.data[self.from_version_key] = OLD_FILE_DEFAULT_FROMVERSION

    def arguments_to_remove(self) -> List[str]:
        """ Finds diff between keys in file and schema of file type
        Returns:
            List of keys that should be deleted in file
        """
        arguments_to_remove = []
        with open(self.schema_path, 'r') as file_obj:
            a = yaml.safe_load(file_obj)
        schema_fields = a.get('mapping').keys()
        file_fields = self.data.keys()
        for field in file_fields:
            if field not in schema_fields:
                arguments_to_remove.append(field)
        return arguments_to_remove

    def set_from_version_key_name(self) -> Union[str, None]:
        """fromversion key is different between yml and json , in yml file : fromversion, in json files : fromVersion"""
        if self.file_type == "yml":
            return 'fromversion'
        elif self.file_type == "json":
            return 'fromVersion'
        return None

    def is_old_file(self, path: str) -> Tuple[dict, bool]:
        """Check whether the file is in git repo or new file.  """
        if path:
            data = get_remote_file(path)
            if not data:
                return {}, False
            else:
                return data, True
        return {}, False

    def initiate_file_validator(self, validator_type):
        """ Run schema validate and file validate of file
        Returns:
            int 0 in case of success 1 otherwise
        """
        print_color('Starting validating files structure', LOG_COLORS.GREEN)
        if self.relative_content_path:
            structure_validator = StructureValidator(self.relative_content_path)
            validator = validator_type(structure_validator)
            if structure_validator.is_valid_file() and validator.is_valid_file(validate_rn=False):
                print_color('The files are valid', LOG_COLORS.GREEN)
                return 0
            else:
                print_color('The files are invalid', LOG_COLORS.RED)
                return 1
        else:
            print_color(f'The file {self.output_file} are not part of content repo, Validator Skipped',
                        LOG_COLORS.YELLOW)