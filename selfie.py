#!/usr/bin/env python
import gi
import time, os
gi.require_version('Gst', '1.0')
from gi.repository import Gst
from gi.repository import GLib

class selfie(object):
  def __init__(self, callback = None, filename = "/tmp/selfie.jpg", delay_s = 1): #exit_function is a callback function which is called when the photo is stored

    Gst.init()

    p = "droidcamsrc  mode=1 camera-device=1 name=cam ! image/jpeg,width=800,height=600 ! filesink name=filesink location={} \n".format(filename)
    p += " cam. ! video/x-raw ! fakesink"
    self.pipeline = Gst.parse_launch(p)

    self.camera = self.pipeline.get_by_name("cam")
    if callback == None :
      callback = self.close        
    self.advise_photo_taken = callback
    self.filename = filename
    if os.path.isfile(filename):
      os.remove(filename)
    
    self.pipeline.set_state(Gst.State.PLAYING)
    
    # Create bus to get events from GStreamer pipeline
    bus = self.pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect('message', self._on_message)
    if delay_s !=0 : #automatically fire photo after delay
      GLib.timeout_add(1000*delay_s, self.take_photo)
            
  def _on_message(self, bus, message):
    '''
    Handle messages received from Gstreamer
    '''
    if message.type == Gst.MessageType.ERROR:
      print('Error {}: {}, {}'.format(message.src.name, *message.parse_error()))
    elif message.type == Gst.MessageType.WARNING:
      err, debug = message.parse_warning()
      print ('Warning: %s' % err, debug)
    elif message.type == Gst.MessageType.ELEMENT:
      if "photo-capture-end;" in message.get_structure().to_string():
        print("photo captured")
        self.advise_photo_taken()

            
  def take_photo(self):
    self.camera.emit("start-capture")

  def close(self):
    print("closing cam")
    self.camera.set_state(Gst.State.NULL)
    #Gst.deinit()
        
        
def on_quit():
  print ("Bye !")
  camera.close()
  mainloop.quit ()

def ownprocess(targetfile = "/tmp/selfie.jpg"):
  global camera, mainloop  
  
  print ('Create camera')
  camera = selfie(callback = on_quit,filename = targetfile)
  mainloop = GLib.MainLoop()
  mainloop.run()

if __name__ == '__main__':

  import signal
  signal.signal(signal.SIGINT, signal.SIG_DFL)
  
  try:
    ownprocess()
  except KeyboardInterrupt:
    mainloop.quit ()


