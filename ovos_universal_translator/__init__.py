from ovos_utils.log import LOG
from ovos_utils.messagebus import FakeBus
from ovos_plugin_manager.language import OVOSLangTranslationFactory
from ovos_plugin_manager.templates.language import LanguageTranslator
from ovos_audio.service import PlaybackService
from ovos_dinkum_listener.service import OVOSDinkumVoiceService
from ovos_stt_plugin_fasterwhisper import FasterWhisperLangClassifier
from typing import Optional, List


def on_ready():
    LOG.info('ready.')


def on_alive():
    LOG.info('alive.')


def on_started():
    LOG.info('started.')


def on_stopping():
    LOG.info('shutting down...')


def on_error(e='Unknown'):
    LOG.error(f'error ({e}).')


class UniversalTranslator(OVOSDinkumVoiceService):
    """STT, VAD, Mic and TTS plugins come from mycroft.conf as usual"""
    def __init__(self, input_languages: List[str],
                 output_languages: List[str],
                 lang_classifier: FasterWhisperLangClassifier,
                 translator: Optional[LanguageTranslator]=None,
                 on_ready=on_ready, on_error=on_error,
                 on_stopping=on_stopping, on_alive=on_alive,
                 on_started=on_started, watchdog=lambda: None):
        super().__init__(on_ready, on_error, on_stopping,
                         on_alive, on_started, watchdog)
        self.input_langs = input_languages
        self.output_langs = output_languages
        self.audio = PlaybackService(bus=self.bus)
        self.translator = translator or OVOSLangTranslationFactory.create()
        self.lang_clf = lang_classifier or FasterWhisperLangClassifier()
        self.validate_languages()

    def validate_languages(self):
        # ensure plugins support configured langs
        for lang in self.input_langs:
            assert lang in self.stt.available_languages
        for lang in self.output_langs:
            assert lang in self.audio.tts.available_languages
            assert lang in self.translator.available_languages

    def _connect_to_bus(self):
        """A messagebus can be added if we need to connect to OVOS
        or send events to other system services"""
        self.bus = FakeBus()
        LOG.info("Launched FakeBus")

    def _stt_audio(self, audio_bytes: bytes, stt_context: dict):
        # language detection here
        lang, lang_probability = self.lang_clf.detect(audio_bytes, self.input_langs)
        stt_context["stt_lang"] = lang
        return stt_context

    def _stt_text(self, text: str, stt_context: dict):
        if isinstance(text, list):
            text = text[0]  # contains alternate transcriptions
        lang = stt_context.get("stt_lang")
        if text and lang:  # handle empty transcripts
            text = text.strip()
            LOG.info(f"Lang: {lang} STT: {text}")
            for target_lang in self.output_langs:
                if target_lang == lang:
                    continue
                LOG.info(f"Translating from {lang} to {target_lang}")
                translated = self.translator.translate(text,
                                                       target=target_lang,
                                                       source=lang)
                LOG.info(f"Speaking in {target_lang}")
                self.audio.tts.execute(translated, lang=target_lang)
