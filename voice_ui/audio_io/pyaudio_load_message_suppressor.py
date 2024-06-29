from contextlib import contextmanager
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll

ERROR_HANDLER_FUNC_1 = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
ERROR_HANDLER_FUNC_2 = CFUNCTYPE(None, c_char_p)


def py_error_handler_1(filename, line, function, err, fmt):  # pragma: no cover
    pass


def py_error_handler_2(err):  # pragma: no cover
    pass


c_error_handler_1 = ERROR_HANDLER_FUNC_1(py_error_handler_1)
c_error_handler_2 = ERROR_HANDLER_FUNC_2(py_error_handler_2)


@contextmanager
def no_alsa_and_jack_errors():  # pragma: no cover
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler_1)

    jack = cdll.LoadLibrary('libjack.so')
    jack.jack_set_error_function(c_error_handler_2)

    yield
    asound.snd_lib_error_set_handler(None)
    jack.jack_set_error_function(None)
