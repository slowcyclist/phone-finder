#!/usr/bin/python3
"""
phone-finder

Damn, where is my phone?! 
Most of the time you'll have simply misplaced it (but unfortunately it is in silent mode...). 
It may also happen that you have lost your phone while outdoors (It happened to me a year ago... I could call the phone, but I had no clue where to look for it! It gave me the motivation for writing this code)
In the worst case, your phone was stollen...

In all these situations, this program can help retrieving your phone.

Features: 
 
- when an incoming sms contains some predefined text, it triggers actions

    -performs gps localization and return the coordinates to the caller
    (this is usefull if you loose your phone outdoors...)
    -switch the phone to non-silent
    -execute an arbitary non-interactive shell command and send the result back via sms
    -establish an ssh link to a predefined host (automatically with key) with reverse tunnel in order to be able to reach the phone's console
    -extensible to do anything else you want (and know how to do it): record sound...

- it listen for incoming calls from a set of predefined numbers
  If the phone is in silent mode and the call is not answered, it (optionally) sends an sms to the caller to warn the phone is silent.
  If the same caller calls a given number of time within a predefined period (say twice within 1 minute, meaning
  this person really needs to talk to you) it switches the phone to non-silent (and the phone rings, of course).
  
- if someone enters a wrong unlock code, it takes a quick selfie, performs gps localization and sends both by email.

All this is written in python which means it is relatively easy to tweak the behavior of the program or expand it

For this to work, the script needs to run continuously in the background (it consumes negligible battery when inactive)
You can do this by starting the script automatically with systemd

You also need to edit the configuration file for setting the predefined sms messages, the preferred callers, the default email address and server, etc.

Don't forget to test all the use case to ensure they'll work as expected when the time comes.


TODO  : handle dual-sims

******************************************************************

P. Joyez copyright 2018
This code is licended under the GPL v3 or later. 

"""
logfilename="phone-finder.log"
configfilename='phone-finder.conf'

import dbus
import sys, time
from gi.repository import GLib
import dbus.mainloop.glib
import os,logging
import subprocess
import configparser
from multiprocessing import Process

#local modules
from dbus_types import *
from gps import *
import selfie

#needed for print() strings with utf-8 characters to console
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)

############################################################
#   In/Out communication
############################################################


def incoming_message(message, details):#, path, interface):
  message = str(message)
  logger.info("received sms message : %s" % (message))
  for key in details:
    val = details[key]
    logger.info("    %s = %s" % (key, val))
  sender = details["Sender"]
  for k in sms_triggers.keys() :
    if k in message :
      sms_triggers[k](sender, message)
  
def send_sms(who, what):
  path = "/ril_0"
  logger.info("Send message '%s' to %s ..." % (what, who))
  mm = dbus.Interface(sys_dbus.get_object('org.ofono', path),'org.ofono.MessageManager')
  properties = mm.GetProperties()
  reports_mem = properties["UseDeliveryReports"]
  #logger.info("reports : %s" %(reports_mem))
  mm.SetProperty("UseDeliveryReports", dbus.Boolean(0))
  path = mm.SendMessage(who, what)
  mm.SetProperty("UseDeliveryReports", dbus.Boolean(int(reports_mem)))
  #logger.info(path)
  
def new_call(name, value):
  global calltimes, caller, watch_hangup, watch_answer
  logger.info("new call")
  #iface = interface[interface.rfind(".") + 1:]
  #logger.info("{%s} [%s] %s %s" % (iface, member, name, dbus2py(value)))
  dic = dbus2py(value)
  if dic['State'] != "incoming" :
    return
  else :
    caller = dic['LineIdentification']
    logger.info ("caller : %s" %(caller))
    if caller in authorized_callers :
      if test_silent_mode():
        logger.info("phone is silent")
        now = time.time()
        calltimes.append([caller,now])
        logger.info(calltimes)
        calltimes = [[who,when] for who, when in calltimes if (now - when < caller_timewindow)] #keep only usefull history
        if len([when for  who, when in calltimes if (who == caller)]) >= caller_repeat :
          set_silent(False)
        elif warn_silent_sms !="" :
          voicecall = dbus.Interface(sys_dbus.get_object('org.ofono', name), 'org.ofono.VoiceCall')
          watch_answer = voicecall.connect_to_signal("PropertyChanged", watch_answer_call)
          watch_hangup = voicecall.connect_to_signal("DisconnectReason", watch_hangup_call)

def watch_hangup_call(reason):
  global caller
  if dbus2py(reason) ==  "remote" : #call was not answered, send sms
    watch_hangup.remove()
    watch_answer.remove()
    send_sms(caller, warn_silent_sms)
    caller = ""
  
def watch_answer_call(name, value):
  print("watch_answer_call :",dbus2py(name)," ",dbus2py(value))
  if dbus2py(name) != "State" :
    return
  if dbus2py(value) ==  "active" : #call answered, stop watching
    watch_hangup.remove()
    watch_answer.remove()

def sms_setup_ssh_remote(sender, message): #message unused
  if ssh_with_key_shell_command == "" :
    send_sms(sender,"ssh_with_key_shell_command not defined !")
    return
  if ensure_online():
    try:
        subprocess.check_call(ssh_with_key_shell_command, shell=True)
        logger.info ("ssh enabled")
        send_sms(sender,"ssh tunnel opened")
    except subprocess.CalledProcessError as e: 
        logger.info ("error opening ssh tunnel : {}\n".format(e))
        send_sms(sender,"ssh tunnel failed : {}".format(e))
  else :
    send_sms(sender,"could not get network connectivity")


############################################################
#   Action scripts and utilities
############################################################
        
def test_silent_mode():
  prof = dbus.Interface(dbus.SessionBus().get_object('com.nokia.profiled', '/com/nokia/profiled'), 'com.nokia.profiled')
  logger.info(prof.get_profile())
  return (prof.get_profile() == "silent")

def set_silent(boolean) :
  """
#this does not really switch sound on (flips the silent icon, though!)
  if boolean :
    profile = "silent"
  else :
    profile = "general"
  cmd = 'dbus-send --type=method_call --dest=com.nokia.profiled /com/nokia/profiled com.nokia.profiled.set_profile string:"%s"'%(profile)
  subprocess.check_call(cmd,stderr=subprocess.STDOUT, shell=True)
  """
# see https://talk.maemo.org/showthread.php?t=100407&page=2
# https://together.jolla.com/question/181809/how-to-using-dbus-from-python-on-sailfish-os/
  if boolean :
    ambience = silent_ambience
  else :
    ambience = not_silent_ambience
  prof = dbus.Interface(dbus.SessionBus().get_object('com.jolla.ambienced', '/com/jolla/ambienced'), 'com.jolla.ambienced')
  prof.setAmbience( dbus.String("file:///usr/share/ambience/%s/%s.ambience"%(ambience, ambience)))

def sms_localization(sender, message) :
  logger.info ("sms localization request from {}... starting gps".format(sender))
  get_localization(lambda msg:exit_gps_sms(sender,msg))

def get_localization(callback) :
  global gps_running
  ensure_online() #faster fix with a-gps
  if not gsp_running :
    gps_running = True
    with gps_locator(callback,gps_localization_timeout,gps_accuracy_target,logger) as gps :
      pass

def exit_gps_sms(sender, msg):
  global gps_running
  gps_running = False    
  send_sms(sender,msg)
  
def ensure_online():
  clear_airplane_mode()
  status = dbus2py(connman_manager.GetProperties())
  if status['State'] == 'online' :
    logger.info("network is available")
    return True
  else :     # turn on cellular data. TODO connect to open wifi if available and no cellular data
    serv=dbus2py(connman_manager.GetServices())
    #print(serv)
    cell = next((k[0] for k in serv if "cellular" in k[0]),None) 
    # this gives the first connman cellular service
    # TODO handle dual SIMS each having data capability
    if cell :
      cellular = dbus.Interface(sys_dbus.get_object("net.connman", cell),'net.connman.Service')
      cellular.SetProperty("AutoConnect", dbus.Boolean(1)) # <-This really connects/disconnects (not the Connect method...)
      time.sleep(1)
      props=dbus2py(cellular.GetProperties())
      print(props)
      return ('Address' in props['IPv4'].keys()) #returns True if IPV4 address attributed. !FIXME IPv4 only for the moment!
    else :
      print("no cellular connexion available")
      return False
      
def clear_airplane_mode():
  status = dbus2py(connman_manager.GetProperties())
  if status["OfflineMode"] :
    logger.info("airplane mode on, turning it off...")
    try:   
      subprocess.check_call("sudo /usr/bin/connmanctl disable offline", shell=True)
      logger.info("airplane mode turned off")
      time.sleep(15) #allow some time to establish connexions
      return True
    except subprocess.CalledProcessError as e: 
      logger.info("error turning airplane mode off, probably lacking line in sudoers")
      return False
  else :
    return True


def device_lock(state):
  global phone_locked
  locking = (dbus2py(state) ==  1)
  if locking and phone_locked: #locking when already locked means a bad unlock code was entered
      logger.info ("Keyboard code failure, sending email")
      pictures.append("/tmp/selfie{}.jpg".format(str(len(pictures))))
      p = Process(target=selfie.ownprocess, args=(pictures[-1],))
      p.start()
      get_localization(gps_exit_email)
      p.join()
  else :
      phone_locked = locking

def gps_exit_email(coords):
  '''#!/usr/bin/python3
  #https://stackoverflow.com/questions/3362600/how-to-send-email-attachments
  '''
  global gps_running, pending_email_signal, pending_email
  gps_running = False
  body = "Someone failed to unlock my phone, check his portrait!\n"
  body += coords
  msg = compose_email("Alert : failed phone unlock!",body,pictures)
  if not (ensure_online() and send_email(msg)) :
    pending_email = content
    pending_email_signal = connman_manager.connect_to_signal("PropertyChanged", send_pending_email)

def send_pending_email(name,value):
  global pending_email_signal, pending_email
  if (dbsu2py(name) !=  'State') or  dbsu2py(value) != 'online' :
    return
  else :
    if send_email(pending_email) :
      pending_email = None
      pending_email_signal.remove()
  
def compose_email(subject,bodytext,images=None):
  
  from email.mime.multipart import MIMEMultipart
  from email.mime.text import MIMEText
  from email.mime.base import MIMEBase
  from email import encoders
  
  msg = MIMEMultipart()
  
  msg['From'] = email_sender
  msg['To'] = email_dest
  msg['Subject'] = subject
  
  msg.attach(MIMEText(bodytext, 'plain'))
  
  for i, pict in enumerate(pictures) :
    imagename = "picture_{}".format(i)
    attachment = open(pic, "rb")
    
    part = MIMEBase('application', 'octet-stream')
    part.set_payload((attachment).read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', "attachment; filename= %s" % imagename)
    
    msg.attach(part)
  return msg.as_string()

def send_email(content):
  import smtplib
  try :
    server = smtplib.SMTP_SSL(host=smtp_server,port= smtp_server_port,timeout=15)
    server.login(email_sender, email_pw)
    server.sendmail(email_sender, email_dest, content)
    server.quit()
    logger.info ("Email sent")
    return True
  except Exception as e:
    logger.info ("Error {} while sending email".format(e))
    return False
  
def sms_run_command (sender, msg):
  idx = msg.find(run_command_separator)
  if (idx < 0) or (idx+len(run_command_separator) == len(msg)):
    send_sms(sender,"error : could not find the command to run\nThe expected separator is : '{}'".format(run_command_separator))
    return
  else:
    cmd = msg[idx+len(run_command_separator):]
    print(cmd)
    reply = ""
    try:
        reply = subprocess.check_output(cmd, shell=True).decode("utf-8")
        logger.info ("cmd run :" + cmd +"\nanswer:\n"+reply)
        send_sms(sender,reply)
    except subprocess.CalledProcessError as e: 
        logger.info ("error running cmd : {1}\n{2}".format(e,reply))
        send_sms(sender,"error running cmd : {1}\n{2}".format(e,reply))

############################################################
#   Initialization : logger, init variables, load configuration...
############################################################


logfile="{0}/{1}".format(sys.path[0], logfilename)
try:
    os.remove(logfile)
except OSError as e:  ## if failed, report it back to the user ##
    print ("Error: %s - %s." % (e.filename, e.strerror))

logging.basicConfig(
    level=logging.INFO,
    #format="%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s",
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(logfile),
        logging.StreamHandler(sys.stdout)
    ])
    
logger = logging.getLogger()

# these variables must have default values
# may be overriden in conf file
gps_localization_timeout = 360
gps_accuracy_target = 10
warn_silent_sms = ""
caller_timewindow = 60
caller_repeat = 2
silent_ambience = "silent"
not_silent_ambience = "origami"
ssh_with_key_shell_command = ""
run_command_separator = "|"
sms_unmute = lambda *args : set_silent(False)
calltimes = []
caller = ""
watch_hangup = None
watch_answer = None
phone_locked = None
pictures = []
gsp_running = False



configfilename = "{0}/{1}".format(sys.path[0],configfilename)
if not os.path.isfile(configfilename) :
  logger.info ("no configuration file... cannot continue")
  exit(1)
else :
  s=open(configfilename,'rb').read().decode("utf-8")
  exec(s)

print([k for k in sms_triggers.keys()])
print( authorized_callers)

############################################################
#   Connect to ofono signals and run main loop
############################################################

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
sys_dbus = dbus.SystemBus()
mainloop = GLib.MainLoop()

connman_manager = dbus.Interface(sys_dbus.get_object("net.connman", "/"),'net.connman.Manager')
  
sys_dbus.add_signal_receiver(new_call, bus_name="org.ofono",	signal_name = "CallAdded")
sys_dbus.add_signal_receiver(incoming_message, bus_name="org.ofono", signal_name = "ImmediateMessage")
sys_dbus.add_signal_receiver(incoming_message, bus_name="org.ofono", signal_name = "IncomingMessage")#,  path_keyword="path", interface_keyword="interface")
devicelock= dbus.Interface(sys_dbus.get_object("org.nemomobile.devicelock", "/devicelock"),'org.nemomobile.lipstick.devicelock')
phone_locked = (dbus2py(devicelock.state()) == 1)
logger.info ("initially locked : "+str(phone_locked))
devicelock.connect_to_signal("stateChanged", device_lock)
clear_airplane_mode() #when the program autostarts, make sure it can receive SMSs... (needs auto-enter-pin too!)
mainloop.run()





