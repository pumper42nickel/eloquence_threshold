#Copyright (C) 2009-2019 eloquence fans
#synthDrivers/eci.py
#todo: possibly add to this
import speech, tones
punctuation = ",.?:;"
punctuation = [x for x in punctuation]
from ctypes import *
import ctypes.wintypes
from ctypes import wintypes
import synthDriverHandler, os, config, re, nvwave, threading, logging
from synthDriverHandler import SynthDriver, VoiceInfo, synthIndexReached, synthDoneSpeaking
from synthDriverHandler import SynthDriver,VoiceInfo
from . import _eloquence
from collections import OrderedDict
import unicodedata

minRate=40
maxRate=150
anticrash_res = {
 re.compile(r'\b(|\d+|\W+)(|un|anti|re)c(ae|\xe6)sur', re.I): r'\1\2seizur',
 re.compile(r"\b(|\d+|\W+)h'(r|v)[e]", re.I): r"\1h ' \2 e",
# re.compile(r"\b(|\d+|\W+)wed[h]esday", re.I): r"\1wed hesday",
re.compile(r'hesday'): ' hesday',
  re.compile(r"\b(|\d+|\W+)tz[s]che", re.I): r"\1tz sche"
}

pause_re = re.compile(r'([a-zA-Z])([.(),:;!?])( |$)')
time_re = re.compile(r"(\d):(\d+):(\d+)")
english_fixes = {
re.compile(r'(\w+)\.([a-zA-Z]+)'): r'\1 dot \2',
re.compile(r'([a-zA-Z0-9_]+)@(\w+)'): r'\1 at \2',
}
french_fixes = {
re.compile(r'([a-zA-Z0-9_]+)@(\w+)'): r'\1 arobase \2',
}
spanish_fixes = {
#for emails
re.compile(r'([a-zA-Z0-9_]+)@(\w+)'): r'\1 arroba \2',
}
variants = {1:"Reed",
2:"Shelley",
3:"Bobby",
4:"Rocko",
5:"Glen",
6:"Sandy",
7:"Grandma",
8:"Grandpa"}

def strip_accents(s):
  return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')  
                  
def normalizeText(s):
  """
  Normalizes  text by removing unicode characters.
  Tries to preserve accented characters if they fall into MBCS encoding page.
  Tries to find closest ASCII characters if accented characters cannot be represented in MBCS.
  """
  result = []
  for c in s:
   try:
    cc = c.encode('mbcs').decode('mbcs')
   except UnicodeEncodeError:
    cc = strip_accents(c)
    # TODO: If synth still crashes on weird characters, check if cc is within MBS codepage, and if not, replace it with "?"
   result.append(cc)
  return "".join(result)

class SynthDriver(synthDriverHandler.SynthDriver):
 supportedSettings=(SynthDriver.VoiceSetting(), SynthDriver.VariantSetting(), SynthDriver.RateSetting(),SynthDriver.PitchSetting(),SynthDriver.InflectionSetting(),SynthDriver.VolumeSetting())
 supportedCommands = {
    speech.IndexCommand,
    speech.CharacterModeCommand,
    speech.LangChangeCommand,
    speech.BreakCommand,
    speech.PitchCommand,
    speech.RateCommand,
    speech.VolumeCommand,
    speech.PhonemeCommand,
 }
 #supportedNotifications = {synthIndexReached, synthDoneSpeaking} 
 description='ETI-Eloquence'
 name='eloquence'
 @classmethod
 def check(cls):
  return _eloquence.eciCheck()
 def __init__(self):
  _eloquence.initialize(self._onIndexReached)
  self.curvoice="enu"
  self.rate=50
  self.variant = "1"

 def speak(self,speechSequence):
  #  print speechSequence
  last = None
  outlist = []
  for item in speechSequence:
   if isinstance(item,str):
    s=str(item)
    s = self.xspeakText(s)
    outlist.append((_eloquence.speak, (s,)))
    last = s
   elif isinstance(item,speech.IndexCommand):
    outlist.append((_eloquence.index, (item.index,)))
  if last is not None and not last.rstrip()[-1] in punctuation:
   outlist.append((_eloquence.speak, ('`p1.',)))
  outlist.append((_eloquence.index, (0xffff,)))
  outlist.append((_eloquence.synth,()))
  _eloquence.synth_queue.put(outlist)
  _eloquence.process()

 def xspeakText(self,text, should_pause=False):
  if _eloquence.params[9] == 65536 or _eloquence.params[9] == 65537: text = resub(english_fixes, text)
  if _eloquence.params[9] == 131072 or _eloquence.params[9] == 131073: text = resub(spanish_fixes, text)
  if _eloquence.params[9] in (196609, 196608): text = resub(french_fixes, text)
  #this converts to ansi for anticrash. If this breaks with foreign langs, we can remove it.
  #text = text.encode('mbcs')
  text = normalizeText(text)
  text = resub(anticrash_res, text)
  text = "`pp0 `vv%d %s" % (self.getVParam(_eloquence.vlm), text.replace('`', ' ')) #no embedded commands
  text = pause_re.sub(r'\1 `p1\2\3', text)
  text = time_re.sub(r'\1:\2 \3', text)
  #if two strings are sent separately, pause between them. This might fix some of the audio issues we're having.
  if should_pause:
   text = text + ' `p1.'
  return text
  #  _eloquence.speak(text, index)
  
  # def cancel(self):
  #  self.dll.eciStop(self.handle)

 def pause(self,switch):
  _eloquence.pause(switch)
  #  self.dll.eciPause(self.handle,switch)

 def terminate(self):
  _eloquence.terminate()

 def _get_rate(self):
  return self._paramToPercent(self.getVParam(_eloquence.rate),minRate,maxRate)

 def _set_rate(self,vl):
  self._rate = self._percentToParam(vl,minRate,maxRate)
  self.setVParam(_eloquence.rate,self._percentToParam(vl,minRate,maxRate))

 def _get_pitch(self):
  return self.getVParam(_eloquence.pitch)

 def _set_pitch(self,vl):
  self.setVParam(_eloquence.pitch,vl)

 def _get_volume(self):
  return self.getVParam(_eloquence.vlm)

 def _set_volume(self,vl):
  self.setVParam(_eloquence.vlm,int(vl))

 def _set_inflection(self,vl):
  vl = int(vl)
  self.setVParam(_eloquence.fluctuation,vl)

 def _get_inflection(self):
  return self.getVParam(_eloquence.fluctuation)

 def _getAvailableVoices(self):
  o = OrderedDict()
  for name in os.listdir(_eloquence.eciPath[:-8]):
   if not name.lower().endswith('.syn'): continue
   info = _eloquence.langs[name.lower()[:-4]]
   o[str(info[0])] = synthDriverHandler.VoiceInfo(str(info[0]), info[1], None)
  return o

 def _get_voice(self):
  return str(_eloquence.params[9])
 def _set_voice(self,vl):
  _eloquence.set_voice(vl)
  self.curvoice = vl
 def getVParam(self,pr):
  return _eloquence.getVParam(pr)

 def setVParam(self, pr,vl):
  _eloquence.setVParam(pr, vl)

 def _get_lastIndex(self):
  #fix?
  return _eloquence.lastindex

 def cancel(self):
  _eloquence.stop()

 def _getAvailableVariants(self):
  
  global variants
  return OrderedDict((str(id), synthDriverHandler.VoiceInfo(str(id), name)) for id, name in variants.items())

 def _set_variant(self, v):
  global variants
  self._variant = v if int(v) in variants else "1"
  _eloquence.setVariant(int(v))
  self.setVParam(_eloquence.rate, self._rate)
  #  if 'eloquence' in config.conf['speech']:
  #   config.conf['speech']['eloquence']['pitch'] = self.pitch

 def _get_variant(self): return self._variant
 
 def _onIndexReached(self, index):
  if index is not None:
   synthIndexReached.notify(synth=self, index=index)
  else:
   synthDoneSpeaking.notify(synth=self)
 

def resub(dct, s):
 for r in dct.keys():
  s = r.sub(dct[r], s)
 return s
