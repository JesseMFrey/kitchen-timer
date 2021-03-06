#!/usr/bin/env python

import argparse
import gi
import re
import sounddevice

from datetime import timedelta
from soundfile import read as wav_read

try:
    import importlib.resources as pkg_resources
except ImportError:
    # Try backported to PY<37 `importlib_resources`.
    import importlib_resources as pkg_resources

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
#from gi.repository import GObject

#GObject.signal_new(
                    #"timer_elapsed",
                    #Gtk.Window,
                    #GObject.SignalFlags.RUN_LAST,
                    #GObject.TYPE_BOOLEAN,
                    #()
                   #)

def parse_time(tstr):
    m = re.match(r'(?:(?P<hours>\d+)h)?\s*' +       #optionally match hours
                 r'(?:(?P<minutes>\d+)m)?\s*' +     #optionally match minutes
                 r'(?:(?P<seconds>\d+)s)?' +        #optionally match seconds
                 r'(?<=\d(?:h|m|s))',               #make sure that something was matched
                 tstr
                 )

    if not m:
        raise ValueError(f'Could not parse \'{tstr}\'')

    args = {}
    for g in ('hours', 'minutes', 'seconds'):
        val = m.group(g)
        if val:
            args[g] = int(val)
    
    return timedelta(**args)

class TimerWindow(Gtk.Window):
    def __init__(self, debug=False):
        Gtk.Window.__init__(self, title="Timer")

        self.debug = debug

        with pkg_resources.path('kitchentimer','alarm.wav') as alarm:
            #load audio for alarm
            self.alarm_audio, self.alarm_fs = wav_read(alarm)

        grid = Gtk.Grid(column_homogeneous=True, column_spacing=10, row_spacing=10)

        self.remain_label = Gtk.Label()
        self.remain_label.set_name('time_text')
        self.remain_label.set_vexpand(True)
        self.remain_label.set_hexpand(True)
        grid.attach(self.remain_label, 0, 0, 3, 1)

        done_button = Gtk.Button(label='Done')
        done_button.set_vexpand(False)
        done_button.connect('clicked', Gtk.main_quit)
        context = done_button.get_style_context()
        context.add_class('botbutton')
        grid.attach(done_button, 0, 1, 1, 1)

        p1_button = Gtk.Button(label='+1m')
        p1_button.set_vexpand(False)
        p1_button.connect('clicked', lambda arg : self.add_elapsed_min(1))
        context = p1_button.get_style_context()
        context.add_class('botbutton')
        grid.attach(p1_button, 1, 1, 1, 1)

        p5_button = Gtk.Button(label='+5m')
        p5_button.set_vexpand(False)
        p5_button.connect('clicked', lambda arg : self.add_elapsed_min(5))
        context = p5_button.get_style_context()
        context.add_class('botbutton')
        grid.attach(p5_button, 2, 1, 1, 1)

        self.add(grid)

    def get_time(self):
        timeout_dialog = TimeoutDialog(self)
        response = timeout_dialog.run()

        if self.debug:
            print(f'Response : {response}')

        if response in (Gtk.ResponseType.OK,
                        Gtk.ResponseType.YES,
                        Gtk.ResponseType.ACCEPT,
                        Gtk.ResponseType.APPLY,
                        ):
            time_str = timeout_dialog.entry.get_text()

            if self.debug:
                print(f'Time : {time_str}')
        
        timeout_dialog.destroy()

        if response in (Gtk.ResponseType.CANCEL,
                        Gtk.ResponseType.DELETE_EVENT,
                        Gtk.ResponseType.CLOSE,
                        Gtk.ResponseType.REJECT,
                        Gtk.ResponseType.NONE,
                        Gtk.ResponseType.NO,
                        ):
            return False

        time = parse_time(time_str)

        self.start_timer(time)

        return True


	# Initialize Timer
    def start_timer(self, time):
        self.original_time =time
        self.remaining_time = time
        self.display_remaining()
        #  this takes 2 args: (how often to update in millisec, the method to run)
        GLib.timeout_add_seconds(1, self.update_remaining)

    def add_elapsed_min(self, add_min):
        self.remaining_time += timedelta(minutes=add_min)

        self.display_remaining()

        #check if alarm should be playing
        if self.remaining_time > timedelta(seconds=0):
            sounddevice.stop()

    def update_remaining(self):
        self.remaining_time -= timedelta(seconds=1)
        self.display_remaining()

        if self.remaining_time == timedelta(seconds=0):
            #self.emit('timer_elapsed')

            #play alarm sound
            sounddevice.play(
                                self.alarm_audio,
                                samplerate=self.alarm_fs,
                                blocking=False,
                                loop=True
                            )

        return True

    def display_remaining(self):
        if self.remaining_time < timedelta(seconds=0):
            time = timedelta(seconds=-1*self.remaining_time.total_seconds())
            tm_str = f'-{time}'
        else:
            tm_str = f' {self.remaining_time}'

        if self.debug:
            print(f'Remaining time : {tm_str}')

        self.remain_label.set_text(tm_str)

    def show_elapsed(self, info):
        elapsed = ElapsedDialog(self)
        elapsed.run()
        elapsed.destroy()


class ElapsedDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Timer Elapsed", transient_for=parent, flags=0)
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            'add 1m', 1,
            'add 5m', 5,
        )

        self.set_default_size(150, 100)

        box = self.get_content_area()

        label = Gtk.Label(label='Timer has elapsed!')
        box.add(label)

        self.show_all()

class TimeoutDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Timer Timeout", transient_for=parent, flags=0)
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        self.set_default_size(150, 100)

        box = self.get_content_area()

        label = Gtk.Label(label='Enter timeout :')
        box.add(label)

        self.entry = Gtk.Entry()
        self.entry.set_text("")
        self.entry.connect('activate',lambda w : self.response(Gtk.ResponseType.OK))

        box.add(self.entry)

        self.show_all()

def main():

    parser = argparse.ArgumentParser(description='Kitchen timer program')
    parser.add_argument('--debug', action='store_true',
            help='Print extra things')

    args = parser.parse_args()

    css_provider = Gtk.CssProvider()
    with pkg_resources.path('kitchentimer','style.css') as css_file:
        css_provider.load_from_path(str(css_file))
    context = Gtk.StyleContext()
    screen = Gdk.Screen.get_default()
    context.add_provider_for_screen(screen, css_provider,
                                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


    win = TimerWindow(debug=args.debug)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    if win.get_time():
        Gtk.main()

if __name__ == '__main__':
    main()

