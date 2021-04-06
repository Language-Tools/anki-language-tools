import logging

import constants
import deck_utils
import languagetools

class MockAnkiUtils():
    def __init__(self, config):
        self.config = config

    def get_config(self):
        return self.config

    def write_config(self, config):
        self.written_config = config

    def get_green_stylesheet(self):
        return constants.GREEN_STYLESHEET

    def get_red_stylesheet(self):
        return constants.RED_STYLESHEET

    def play_anki_sound_tag(self, text):
        self.last_played_sound_tag = text

    def get_deckid_modelid_pairs(self):
        return self.deckid_modelid_pairs

    def get_model(self, model_id):
        # should return a dict which has flds
        return self.models[model_id]

    def get_deck(self, deck_id):
        return self.decks[deck_id]

    def run_in_background(self, task_fn, task_done_fn):
        # just run the two tasks immediately
        result = task_fn()
        task_done_fn(result)

    def run_on_main(self, task_fn):
        # just run the task immediately
        task_fn()

    def critical_message(self, message, parent):
        logging.info(f'critical error message: {message}')
        self.critical_message = message

class MockCloudLanguageTools():
    def __init__(self):
        self.language_list = {
            'en': 'English',
            'zh_cn': 'Chinese'
        }
        self.translation_language_list = [
            {
                'service': "Azure",
                'language_code': "en",
                'language_name': "English",
                'language_id': "en"
            },
            {
                'service': "Azure",
                'language_code': "zh_cn",
                'language_name': "Chinese",
                'language_id': "zh-hans"
            },            
        ]
        self.transliteration_language_list = [] # todo fill this out


    def get_language_list(self):
        return self.language_list

    def get_translation_language_list(self):
        return self.translation_language_list

    def get_transliteration_language_list(self):
        return self.transliteration_language_list

    def api_key_validate_query(self, api_key):
        return {
            'key_valid': True
        }     

class TestConfigGenerator():
    def __init__(self):
        self.deck_id = 42001
        self.model_id = 43001
        self.model_name = 'note-type'
        self.deck_name = 'deck 1'
        self.field_chinese = 'Chinese'
        self.field_english = 'English'
        self.field_sound = 'Sound'
        self.all_fields = [self.field_chinese, self.field_english, self.field_sound]

        self.chinese_voice_key = 'chinese voice'
        self.chinese_voice_description = 'this is a chinese voice'

    # different languagetools configs available
    # =========================================

    def get_default_config(self):
        languagetools_config = {
            'api_key': 'yoyo',
            constants.CONFIG_DECK_LANGUAGES: {
                self.model_name: {
                    self.deck_name: {
                        self.field_chinese: 'zh_cn',
                        self.field_english: 'en',
                        self.field_sound: 'sound'
                    }
                }
            },
            constants.CONFIG_VOICE_SELECTION: {
                'zh_cn': {
                    'voice_key': self.chinese_voice_key,
                    'voice_description': self.chinese_voice_description
                }
            }

        }
        return languagetools_config

    def get_config_no_language_mapping(self):
        base_config = self.get_default_config()
        base_config[constants.CONFIG_DECK_LANGUAGES] = {}
        return base_config

    def get_config_batch_audio(self):
        base_config = self.get_default_config()
        base_config[constants.CONFIG_BATCH_AUDIO] = {
            self.model_name: {
                self.deck_name: {
                   self.field_sound: self.field_chinese
                }
            }
        }
        return base_config

    def get_languagetools_config(self, scenario):

        fn_map = {
            'default': self.get_default_config,
            'no_language_mapping': self.get_config_no_language_mapping,
            'batch_audio': self.get_config_batch_audio
        }

        fn_instance = fn_map[scenario]
        return fn_instance()


    def get_model_map(self):
        return {
            self.model_id: {
                'name': self.model_name,
                'flds': [
                    {'name': self.field_chinese},
                    {'name': self.field_english},
                    {'name': self.field_sound}
                ]
            }
        }
    
    def get_deck_map(self):
        return {
            self.deck_id: {
                'name': self.deck_name
            }
        }

    def get_deckid_modelid_pairs(self):
        return [
            [self.deck_id, self.model_id]
        ]        

    def build_languagetools_instance(self, scenario):
        languagetools_config = self.get_languagetools_config(scenario)
        mock_cloudlanguagetools = MockCloudLanguageTools()

        anki_utils = MockAnkiUtils(languagetools_config)
        deckutils = deck_utils.DeckUtils(anki_utils)
        mock_language_tools = languagetools.LanguageTools(anki_utils, deckutils, mock_cloudlanguagetools)
        mock_language_tools.initialize()

        anki_utils.models = self.get_model_map()
        anki_utils.decks = self.get_deck_map()
        anki_utils.deckid_modelid_pairs = self.get_deckid_modelid_pairs()

        return mock_language_tools