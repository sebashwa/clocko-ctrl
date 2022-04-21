class TextFormatting:
    @staticmethod
    def split_for_wrapping(text, width):
        if len(text) == 0:
            return text

        words = text.split(" ")
        result = [words.pop(0)]

        for word in words:
            index = len(result) - 1
            updated_line = result[index] + f" {word}"

            if len(updated_line) <= width:
                result[index] = updated_line
            else:
                result.append(word)

        return result

    @staticmethod
    def format_time(ms):
        total_seconds = int(ms / 1000)
        hours = int(total_seconds / 60 / 60)
        seconds_minus_hours = total_seconds - hours * 60 * 60
        minutes = int(seconds_minus_hours / 60)
        seconds = seconds_minus_hours - minutes * 60

        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)



class TextScrolling:
    text = None

    @classmethod
    def maybe_scroll(cls, text, width):
        if len(text) <= width:
            cls.text = None
            return text, False
        elif text != cls.text:
            cls.text = text
            cls.width = width
            cls.current_segment = text[0:width]
            cls.forwards = True
            cls.current_index = 0
            cls.freeze_counter = 0
        return cls.current_segment, True

    @classmethod
    def modify_index(cls):
        if cls.forwards:
            cls.current_index += 1
        else:
            cls.current_index -= 1

    @classmethod
    def turnaround_index(cls):
        if cls.forwards:
            return len(cls.text) - cls.width
        else:
            return 0

    @classmethod
    def freeze_index(cls):
        if cls.forwards:
            return 0
        else:
            return len(cls.text) - cls.width

    @classmethod
    def scroll(cls, _t=None):
        if cls.text is None:
            return

        if cls.current_index == cls.freeze_index():
            if cls.freeze_counter < 2:
                cls.freeze_counter += 1
            else:
                cls.freeze_counter = 0
                cls.modify_index()
        elif cls.current_index == cls.turnaround_index():
            cls.forwards = not cls.forwards
        else:
            cls.modify_index()

        cls.current_segment = cls.text[cls.current_index:cls.current_index + cls.width]
        return cls.current_segment



