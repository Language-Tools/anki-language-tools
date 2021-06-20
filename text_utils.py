import sys
import anki.utils
import re

if hasattr(sys, '_pytest_mode'):
    import constants
else:
    from . import constants

class TextReplacement():
    def __init__(self, options):
        self.pattern = options['pattern']
        self.replace = options['replace']
        self.transformation_type_map = {}
        for transformation_type in constants.TransformationType:
            self.transformation_type_map[transformation_type] = options.get(transformation_type.name, False)

    def process(self, text, transformation_type):
        result = text
        if self.transformation_type_map[transformation_type]:
            result = re.sub(self.pattern, self.replace, text)
        return result

class TextUtils():
    def __init__(self, options):
        self.options = options
        replacements_array = self.options.get('replacements', [])
        self.replacements = [TextReplacement(replacement) for replacement in replacements_array]

    def is_empty(self, text):
        stripped_field_value = anki.utils.htmlToTextLine(text)
        return len(stripped_field_value) == 0

    def process(self, text, transformation_type: constants.TransformationType):
        result = anki.utils.htmlToTextLine(text)

        # apply replacements
        for replacement in self.replacements:
            result = replacement.process(result, transformation_type)

        return result