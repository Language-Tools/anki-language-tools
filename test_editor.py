import testing_utils
import editor_processing

def test_process_choosetranslation(qtbot):
    # pytest test_editor.py -rPP -k test_process_choosetranslation

    config_gen = testing_utils.TestConfigGenerator()
    mock_language_tools = config_gen.build_languagetools_instance('batch_translation')

    mock_language_tools.cloud_language_tools.translate_all_result = {
        '老人家': {
            'serviceA': 'first translation A',
            'serviceB': 'second translation B'
        }
    }

    bridge_str = 'choosetranslation:1'

    # when the choose translation dialog comes up, we should pick serviceB
    mock_language_tools.anki_utils.display_dialog_behavior = 'choose_serviceB'

    editor = config_gen.get_mock_editor_with_note(config_gen.note_id_1)
    editor_processing.process_choosetranslation(editor,  mock_language_tools, bridge_str)

    assert mock_language_tools.anki_utils.editor_set_field_value_called['field_index'] == 1
    assert mock_language_tools.anki_utils.editor_set_field_value_called['text'] == 'second translation B'


def test_process_choosetranslation_cancel(qtbot):
    # pytest test_editor.py -rPP -k test_process_choosetranslation_cancel

    config_gen = testing_utils.TestConfigGenerator()
    mock_language_tools = config_gen.build_languagetools_instance('batch_translation')

    mock_language_tools.cloud_language_tools.translate_all_result = {
        '老人家': {
            'serviceA': 'first translation A',
            'serviceB': 'second translation B'
        }
    }

    bridge_str = 'choosetranslation:1'

    # when the choose translation dialog comes up, we should pick serviceB
    mock_language_tools.anki_utils.display_dialog_behavior = 'cancel'

    editor = config_gen.get_mock_editor_with_note(config_gen.note_id_1)
    editor_processing.process_choosetranslation(editor,  mock_language_tools, bridge_str)

    assert mock_language_tools.anki_utils.editor_set_field_value_called == None
    