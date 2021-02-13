#python imports
import json
import urllib.parse
from typing import List, Dict

# anki imports
import aqt
import aqt.gui_hooks
import aqt.editor
import aqt.webview
import aqt.addcards
import anki.notes
import anki.models

# addon imports
from .languagetools import LanguageTools, DeckNoteTypeField, build_deck_note_type, build_deck_note_type_from_note, build_deck_note_type_from_note_card, build_deck_note_type_from_addcard, LanguageToolsRequestError
from . import constants


def get_field_id(deck_note_type_field: DeckNoteTypeField):
    model = aqt.mw.col.models.get(deck_note_type_field.deck_note_type.model_id)
    fields = model['flds']
    field_names = [x['name'] for x in fields]
    field_index = field_names.index(deck_note_type_field.field_name)
    return field_index    

def add_loading_indicator(editor: aqt.editor.Editor, field_index, field_name):
    js_command = f"add_loading_indicator({field_index}, '{field_name}')"
    print(js_command)
    editor.web.eval(js_command)

def remove_inline_translation_changes(languagetools: LanguageTools, editor: aqt.editor.Editor, deck_note_type_field: DeckNoteTypeField):
    field_index = get_field_id(deck_note_type_field)
    js_command = f"remove_inline_field('{constants.EDITOR_WEB_FIELD_ID_TRANSLATION}', {field_index})"
    editor.web.eval(js_command)

def apply_inline_translation_changes(languagetools: LanguageTools, editor: aqt.editor.Editor, deck_note_type_field: DeckNoteTypeField, translation_option):
    # first, remove any inline translation which may be present already
    remove_inline_translation_changes(languagetools, editor, deck_note_type_field)

    field_index = get_field_id(deck_note_type_field)
    editor.web.eval(f"add_inline_field('{constants.EDITOR_WEB_FIELD_ID_TRANSLATION}', {field_index}, 'Translation')")

    note = editor.note
    field_value = note[deck_note_type_field.field_name]
    load_inline_translation(languagetools, editor, field_value, deck_note_type_field, translation_option)

def load_inline_translation(languagetools, editor: aqt.editor.Editor, field_value: str, deck_note_type_field: DeckNoteTypeField, translation_option: Dict):
    field_index = get_field_id(deck_note_type_field)

    # now, we need to do the translation, asynchronously
    # prepare lambdas
    #     
    def get_request_translation_lambda(languagetools, field_value, translation_option):
        def request_translation():
            return languagetools.get_translation_async(field_value, translation_option)
        return request_translation

    def get_apply_translation_lambda(languagetools, editor, field_index):
        def apply_translation(future_result):
            translation_response = future_result.result()
            translated_text = languagetools.interpret_translation_response_async(translation_response)
            js_command = f"""set_inline_field_value('{constants.EDITOR_WEB_FIELD_ID_TRANSLATION}', {field_index}, "{translated_text}")"""
            editor.web.eval(js_command)
        return apply_translation

    aqt.mw.taskman.run_in_background(get_request_translation_lambda(languagetools, field_value, translation_option), 
                                     get_apply_translation_lambda(languagetools, editor, field_index))


# generic function to load a transformation asynchronously (translation / transliteration / audio)
def load_transformation(languagetools, editor: aqt.editor.Editor, original_note_id, field_value: str, to_deck_note_type_field: DeckNoteTypeField, request_transformation_fn, interpret_response_fn):
    field_index = get_field_id(to_deck_note_type_field)

    def apply_field_value(field_index, result_text):
        # set the field value on the note
        editor.note.fields[field_index] = result_text
        # update the webview
        js_command = f"""set_field_value({field_index}, "{result_text}")"""
        editor.web.eval(js_command)        

    # is the source field empty ?
    if languagetools.field_empty(field_value):
        apply_field_value(field_index, '')
        return

    def get_apply_transformation_lambda(languagetools, editor, field_index, original_note_id, interpret_response_fn):
        def apply_transformation(future_result):
            if editor.note == None:
                # user has left the editor
                return
            if original_note_id != 0:
                if editor.note.id != original_note_id:
                    # user switched to a different note, ignore
                    return

            transformation_response = future_result.result()
            try:
                result_text = interpret_response_fn(transformation_response)
                apply_field_value(field_index, result_text)
            except LanguageToolsRequestError as e:
                aqt.utils.showCritical(str(e), title=constants.ADDON_NAME)
        return apply_transformation

    aqt.mw.taskman.run_in_background(request_transformation_fn, 
                                     get_apply_transformation_lambda(languagetools, editor, field_index, original_note_id, interpret_response_fn))



def load_translation(languagetools, editor: aqt.editor.Editor, original_note_id, field_value: str, to_deck_note_type_field: DeckNoteTypeField, translation_option: Dict):
    def get_request_translation_lambda(languagetools, field_value, translation_option):
        def request_translation():
            return languagetools.get_translation_async(field_value, translation_option)
        return request_translation
    interpret_response_fn = languagetools.interpret_translation_response_async

    load_transformation(languagetools, editor, original_note_id, field_value, to_deck_note_type_field, get_request_translation_lambda(languagetools, field_value, translation_option), interpret_response_fn)


def load_transliteration(languagetools, editor: aqt.editor.Editor, original_note_id, field_value: str, to_deck_note_type_field: DeckNoteTypeField, transliteration_option: Dict):
    def get_request_transliteration_lambda(languagetools, field_value, transliteration_option):
        def request_transliteration():
            return languagetools.get_transliteration_async(field_value, transliteration_option)
        return request_transliteration
    interpret_response_fn = languagetools.interpret_transliteration_response_async

    load_transformation(languagetools, editor, original_note_id, field_value, to_deck_note_type_field, get_request_transliteration_lambda(languagetools, field_value, transliteration_option), interpret_response_fn)


def load_audio(languagetools, editor: aqt.editor.Editor, original_note_id, field_value: str, to_deck_note_type_field: DeckNoteTypeField, voice: Dict):
    def get_request_audio_lambda(languagetools, field_value, voice):
        def request_audio():
            try:
                return languagetools.generate_audio_tag_collection(field_value, voice)
            except LanguageToolsRequestError as err:
                return {'error': str(err)}
        return request_audio

    def interpret_response_fn(response):
        if 'error' in response:
            # just re-raise
            raise LanguageToolsRequestError('Could not generate audio: ' + response['error'])
        sound_tag = response['sound_tag']
        full_filename = response['full_filename']
        if sound_tag == None:
            return ''
        # sound is valid, play sound
        aqt.sound.av_player.play_file(full_filename)            
        return sound_tag

    load_transformation(languagetools, editor, original_note_id, field_value, to_deck_note_type_field, get_request_audio_lambda(languagetools, field_value, voice), interpret_response_fn)


def init(languagetools):
    aqt.mw.addonManager.setWebExports(__name__, r".*(css|js)")

    def on_webview_will_set_content(web_content: aqt.webview.WebContent, context):
        if not isinstance(context, aqt.editor.Editor):
            return
        addon_package = aqt.mw.addonManager.addonFromModule(__name__)
        javascript_path = f"/_addons/{addon_package}/editor_javascript.js"
        web_content.js.insert(0,  javascript_path)

    def loadNote(editor: aqt.editor.Editor):
        note = editor.note
        # can we get the card from the editor ?
        if editor.card != None:
            deck_note_type = build_deck_note_type_from_note_card(note, editor.card)
        else:
            deck_note_type = build_deck_note_type_from_note(note)
        # print(f'loadNote, deck_note_type: {deck_note_type}')

        model = note.model()
        fields = model['flds']
        for index, field in enumerate(fields):
            field_name = field['name']
            add_loading_indicator(editor, index, field_name)

        return

        inline_translations = languagetools.get_inline_translations(deck_note_type)
        # print(f'loadNote {deck_note_type} inline_translations: {inline_translations}')

        for field_name, target_language in inline_translations.items():
            deck_note_type_field = DeckNoteTypeField(deck_note_type, field_name)
            apply_inline_translation_changes(languagetools, editor, deck_note_type_field, target_language)

    def onBridge(handled, str, editor):
        # return handled # don't do anything for now
        if not isinstance(editor, aqt.editor.Editor):
            return handled

        if languagetools.get_apply_updates_automatically() == False:
            # user doesn't want updates as they type
            return handled

        if str.startswith("key:"):
            # print(str)
            components = str.split(':')
            if len(components) >= 4:
                field_index_str = components[1]
                note_id_str = components[2]
                field_value = ':'.join(components[3:])
                field_index = int(field_index_str)
                note_id = int(note_id_str)
                note = editor.note
                note_id = note.id

                if editor.addMode:
                    deck_note_type = build_deck_note_type_from_addcard(note, editor.parentWindow)
                    #print(f'deck_note_type: {deck_note_type}')
                else:
                    deck_note_type = build_deck_note_type_from_note_card(note, editor.card)
                    # print(f'deck_note_type: {deck_note_type}')

                from_deck_note_type_field = languagetools.get_deck_note_type_field_from_fieldindex(deck_note_type, field_index)

                original_field_value = note[from_deck_note_type_field.field_name]

                # print(f'new field value: [{field_value}] original field value: [{original_field_value}]')

                if field_value != original_field_value:
                    # only do something if the field has changed

                    # do we have translation rules for this deck_note_type
                    translation_settings = languagetools.get_batch_translation_settings(deck_note_type)
                    relevant_settings = {to_field:value for (to_field,value) in translation_settings.items() if value['from_field'] == from_deck_note_type_field.field_name}
                    for to_field, value in relevant_settings.items():
                        to_deck_note_type_field = DeckNoteTypeField(deck_note_type, to_field)
                        load_translation(languagetools, editor, note_id, field_value, to_deck_note_type_field, value['translation_option'])

                    # do we have transliteration rules for this deck_note_type
                    transliteration_settings = languagetools.get_batch_transliteration_settings(deck_note_type)
                    relevant_settings = {to_field:value for (to_field,value) in transliteration_settings.items() if value['from_field'] == from_deck_note_type_field.field_name}
                    for to_field, value in relevant_settings.items():
                        to_deck_note_type_field = DeckNoteTypeField(deck_note_type, to_field)
                        load_transliteration(languagetools, editor, note_id, field_value, to_deck_note_type_field, value['transliteration_option'])

                    # do we have any audio rules for this deck_note_type
                    audio_settings = languagetools.get_batch_audio_settings(deck_note_type)
                    relevant_settings = {to_field:from_field for (to_field,from_field) in audio_settings.items() if from_field == from_deck_note_type_field.field_name}
                    for to_field, from_field in relevant_settings.items():
                        to_deck_note_type_field = DeckNoteTypeField(deck_note_type, to_field)
                        # get the from language
                        from_language = languagetools.get_language(from_deck_note_type_field)
                        if from_language != None:
                            # get voice for this language
                            voice_settings = languagetools.get_voice_selection_settings()
                            if from_language in voice_settings:
                                voice = voice_settings[from_language]
                                load_audio(languagetools, editor, note_id, field_value, to_deck_note_type_field, voice)



        return handled


    aqt.gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
    aqt.gui_hooks.editor_did_load_note.append(loadNote)
    aqt.gui_hooks.webview_did_receive_js_message.append(onBridge)
