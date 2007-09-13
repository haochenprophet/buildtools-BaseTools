## @file
# Common routines used by all tools
#
# Copyright (c) 2007, Intel Corporation
# All rights reserved. This program and the accompanying materials
# are licensed and made available under the terms and conditions of the BSD License
# which accompanies this distribution.  The full text of the license may be found at
# http://opensource.org/licenses/bsd-license.php
#
# THE PROGRAM IS DISTRIBUTED UNDER THE BSD LICENSE ON AN "AS IS" BASIS,
# WITHOUT WARRANTIES OR REPRESENTATIONS OF ANY KIND, EITHER EXPRESS OR IMPLIED.
#

##
# Import Modules
#
import os
import sys
import string
import thread
import threading
import time

## callback routine for processing variable option
#
# This function can be used to process variable number of option values. The
# typical usage of it is specify architecure list on command line.
# (e.g. <tool> -a IA32 X64 IPF)
#
# @param  Option        Standard callback function parameter
# @param  OptionString  Standard callback function parameter
# @param  Value         Standard callback function parameter
# @param  Parser        Standard callback function parameter
#
# @retval
#
def ProcessVariableArgument(Option, OptionString, Value, Parser):
    assert Value is None
    Value = []
    RawArgs = Parser.rargs
    while RawArgs:
        Arg = RawArgs[0]
        if (Arg[:2] == "--" and len(Arg) > 2) or \
           (Arg[:1] == "-" and len(Arg) > 1 and Arg[1] != "-"):
            break
        Value.append(Arg)
        del RawArgs[0]
    setattr(Parser.values, Option.dest, Value)

def GuidStringToGuidStructureString(Guid):
  GuidList = Guid.split('-')
  Result = '{'
  for Index in range(0,3,1):
    Result = Result + '0x' + GuidList[Index] + ', '
  Result = Result + '{0x' + GuidList[3][0:2] + ', 0x' + GuidList[3][2:4]
  for Index in range(0,12,2):
    Result = Result + ', 0x' + GuidList[4][Index:Index+2]
  Result += '}}'
  return Result

def GuidStructureStringToGuidString(GuidValue):
    guidValueString = GuidValue.lower().replace("{", "").replace("}", "").replace(" ", "")
    guidValueList = guidValueString.split(",")
    if len(guidValueList) != 11:
        raise AutoGenError(msg="Invalid GUID value string %s" % GuidValue)
    return "%08x-%04x-%04x-%02x%02x-%02x%02x%02x%02x%02x%02x" % (
            int(guidValueList[0], 16),
            int(guidValueList[1], 16),
            int(guidValueList[2], 16),
            int(guidValueList[3], 16),
            int(guidValueList[4], 16),
            int(guidValueList[5], 16),
            int(guidValueList[6], 16),
            int(guidValueList[7], 16),
            int(guidValueList[8], 16),
            int(guidValueList[9], 16),
            int(guidValueList[10], 16)
            )

def GuidStructureStringToGuidValueName(GuidValue):
    guidValueString = GuidValue.lower().replace("{", "").replace("}", "").replace(" ", "")
    guidValueList = guidValueString.split(",")
    if len(guidValueList) != 11:
        raise AutoGenError(msg="Invalid GUID value string %s" % GuidValue)
    return "%08x_%04x_%04x_%02x%02x_%02x%02x%02x%02x%02x%02x" % (
            int(guidValueList[0], 16),
            int(guidValueList[1], 16),
            int(guidValueList[2], 16),
            int(guidValueList[3], 16),
            int(guidValueList[4], 16),
            int(guidValueList[5], 16),
            int(guidValueList[6], 16),
            int(guidValueList[7], 16),
            int(guidValueList[8], 16),
            int(guidValueList[9], 16),
            int(guidValueList[10], 16)
            )

def CreateDirectory(Directory):
    if not os.access(Directory, os.F_OK):
        os.makedirs(Directory)

def SaveFileOnChange(File, Content, IsBinaryFile=False):
    if IsBinaryFile:
        BinaryFlag = 'b'
    else:
        BinaryFlag = ''
    Fd = None
    if os.path.exists(File):
        Fd = open(File, "r"+BinaryFlag)
        if Content == Fd.read():
            Fd.close()
            return False
        Fd.close()
    CreateDirectory(os.path.dirname(File))
    Fd = open(File, "w"+BinaryFlag)
    Fd.write(Content)
    Fd.close()
    return True

class TemplateString(object):
    def __init__(self):
        self.String = ''

    def __str__(self):
        return self.String

    def Append(self, AppendString, Dictionary=None):
        if Dictionary == None:
            self.String += AppendString
            return

        while AppendString.find('${BEGIN}') >= 0:
            Start = AppendString.find('${BEGIN}')
            End   = AppendString.find('${END}')
            SubString = AppendString[AppendString.find('${BEGIN}'):AppendString.find('${END}')+6]

            RepeatTime = -1
            NewDict = {"BEGIN":"", "END":""}
            for Key in Dictionary:
                if SubString.find('$' + Key) >= 0 or SubString.find('${' + Key + '}') >= 0:
                    Value = Dictionary[Key]
                    if type(Value) != type([]):
                        NewDict[Key] = Value
                        continue
                    if RepeatTime < 0:
                        RepeatTime = len(Value)
                    elif RepeatTime != len(Value):
                        raise AutoGenError(msg=Key + " has different repeat time from others!")
                    NewDict[Key] = ""

            NewString = ''
            for Index in range(0, RepeatTime):
                for Key in NewDict:
                    if Key == "BEGIN" or Key == "END" or type(Dictionary[Key]) != type([]):
                        continue
                    NewDict[Key] = Dictionary[Key][Index]
                NewString += string.Template(SubString).safe_substitute(NewDict)
            AppendString = AppendString[0:Start] + NewString + AppendString[End + 6:]

        NewDict = {}
        for Key in Dictionary:
            if type(Dictionary[Key]) == type([]):
                continue
            NewDict[Key] = Dictionary[Key]
        self.String += string.Template(AppendString).safe_substitute(NewDict)

class Progressor:
    def __init__(self, OpenMessage="", CloseMessage="", ProgressChar='.', Interval=1):
        self.StopFlag = threading.Event()
        self.StopFlag.clear()

        self.ProgressThread = None
        self.PromptMessage = OpenMessage
        self.CodaMessage = CloseMessage
        self.ProgressChar = ProgressChar
        self.Interval = Interval

    def Start(self):
        self.ProgressThread = threading.Thread(target=self._ProgressThreadEntry)
        self.ProgressThread.setDaemon(True)
        self.ProgressThread.start()

    def Stop(self):
        self.StopFlag.set()
        self.ProgressThread.join()
        self.ProgressThread = None

    def _ProgressThreadEntry(self):
        print self.PromptMessage,
        while not self.StopFlag.isSet():
            time.sleep(self.Interval)
            print self.ProgressChar,
        print self.CodaMessage
