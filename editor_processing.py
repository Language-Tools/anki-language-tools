import logging
import sys

if hasattr(sys, '_pytest_mode'):
    import errors
    import dialog_choosetranslation
else:
    from . import errors
    from . import dialog_choosetranslation

class EditorManager():
    def __init__(self, languagetools):
        self.languagetools = languagetools

    def process_choosetranslation(self, editor, str):
        try:
            logging.debug(f'choosetranslation command: [{str}]')
            components = str.split(':')
            field_index_str = components[1]
            field_index = int(field_index_str)

            note = editor.note
            current_translation_text = note.fields[field_index]

            deck_note_type = self.languagetools.deck_utils.build_deck_note_type_from_editor(editor)

            target_dntf = self.languagetools.deck_utils.get_dntf_from_fieldindex(deck_note_type, field_index)
            translation_from_field = self.languagetools.get_batch_translation_setting_field(target_dntf)
            from_field = translation_from_field['from_field']
            from_dntf = self.languagetools.deck_utils.build_dntf_from_dnt(deck_note_type, from_field)
            from_text = note[from_field]

            logging.debug(f'from field: {from_dntf} target field: {target_dntf}')

            # get to and from languages
            from_language = self.languagetools.get_language(from_dntf)
            to_language = self.languagetools.get_language(target_dntf)
            if from_language == None:
                raise errors.FieldLanguageMappingError(from_dntf)
            if to_language == None:
                raise errors.FieldLanguageMappingError(target_dntf)

            def load_translation_all():
                return self.languagetools.get_translation_all(from_text, from_language, to_language)

            def get_done_callback(from_text, from_language, to_language, editor, field_index):
                def load_translation_all_done(fut):
                    self.languagetools.anki_utils.stop_progress_bar()
                    data = fut.result()
                    # logging.debug(f'all translations: {data}')
                    dialog = dialog_choosetranslation.prepare_dialog(self.languagetools, from_text, from_language, to_language, data)
                    retval = self.languagetools.anki_utils.display_dialog(dialog)
                    if retval == True:
                        chosen_translation = dialog.selected_translation
                        #logging.debug(f'chosen translation: {chosen_translation}')
                        self.languagetools.anki_utils.editor_set_field_value(editor, field_index, chosen_translation)

                return load_translation_all_done

            self.languagetools.anki_utils.show_progress_bar("retrieving all translations")
            self.languagetools.anki_utils.run_in_background(load_translation_all, get_done_callback(from_text, from_language, to_language, editor, field_index))
        except Exception as e:
            self.languagetools.anki_utils.critical_message(str(e))
