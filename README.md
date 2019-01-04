# phone-finder
Damn, where is my phone?!

Most of the time you'll have simply misplaced it (but unfortunately it is in silent mode...).

It may also happen that you have lost your phone while outdoors (It happened to me... I could call the phone, but I had no clue where to look for it! It gave me the motivation for writing this code)

In the worst case, your phone was stollen...


**In all these situations, this program can help retrieving your phone.**

## Features: 
 
* When an incoming SMS contains some predefined text, it triggers actions

    * Switch the phone to non-silent
    * Performs gps localization and return the coordinates to the caller (this is usefull if you loose your phone outdoors...)
    * Execute an arbitary non-interactive shell command and send the result back via sms
    * Establish an ssh link to a predefined host (automatically with key) with reverse tunnel in order to be able to reach the phone's console
    * Extensible to do anything else you want (and know how to do it): record sound...

* Watch for incoming calls from a set of predefined numbers
  If the phone is in silent mode and the call is not answered, it (optionally) sends an sms to the caller to warn the phone is silent.
  If the same caller calls a given number of time within a predefined period (say twice within 1 minute, meaning
  this person really wants to talk to you) it switches the phone to non-silent (and the phone rings, of course).
  
* If someone enters a wrong unlock code, it takes a quick selfie, performs gps localization and sends both by email.

## Configuration
For this to work, the script needs to run continuously in the background (it consumes negligible battery when inactive)
You can do this by starting the script automatically with systemd

You also need to edit the configuration file for setting the predefined sms messages, the preferred callers, the default email address and server, etc.

Don't forget to test all the use cases to ensure they'll work as expected when the time comes.

## Installation

## Technical details
All this is written in python which means it is relatively easy to tweak the behavior of the program or expand it.

TODO  : handle dual-sims
