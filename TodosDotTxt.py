#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import sublime
import sublime_plugin
import webbrowser
import datetime
import codecs
from operator import attrgetter

if int(sublime.version()) < 3000:
    import locale


_target = None
_user_input = None
_display = True


###############################################
REGEX_DATE = "20[0-9][0-9]-[0-1][0-9]-[0-3][0-9]"
FORMAT_DATE = "%Y-%m-%d "
REGEX_TODO  = re.compile( '^(x )?(' + REGEX_DATE + ' )?(?:\(([A-E])\) )?(' + REGEX_DATE + ' )?(.*)$')
PRIORITIES = [ "A", "B", "C", "D", "E" ]

###############################################
SETT_TODOFILE = "~\\Dropbox\\markdown\\todo.txt"

###############################################
def get_todofile_path():
    sett = sublime.load_settings('TodosDotTxt.sublime-settings')
    return sett.get( 'todos_file' )

class TodoLine:

    def __init__( self, text ):
        self.line = text
        self.priority      = None
        self.done          = False
        self.creation_date = None
        self.done_date     = None
        self.text          = ""
        self.valid         = False

        self.parse()

    def parse( self ) :
        res = REGEX_TODO.match( self.line )
        if not res :
            return

        self.valid = True
        self.done = res.group( 1 ) != None

        if self.done and res.group( 2 ) :
            self.done_date = datetime.datetime.strptime( res.group( 2 ), FORMAT_DATE )
        elif not self.done and res.group( 2 ) :
            self.creation_date = datetime.datetime.strptime( res.group( 2 ), FORMAT_DATE )

        if res.group( 4 ) :
            self.creation_date = datetime.datetime.strptime( res.group( 4 ), FORMAT_DATE )

        self.priority = res.group( 3 )
        self.txt = res.group( 5 )


    def output_line( self ):
        out = ""
        if self.done :
            out += "x "
        if self.done and self.done_date :
            out += self.done_date.strftime( FORMAT_DATE )
        if self.priority :
            out += "(" + self.priority + ") "
        if self.creation_date :
            out += self.creation_date.strftime( FORMAT_DATE )
        out += self.txt
        return out


###############################################
class TodosDotTxtIncreasePriority(sublime_plugin.TextCommand):
    def is_enabled( self ):
        return self.view.file_name().endswith( "todo.txt" )
    def run(self, edit):
        for region in self.view.sel():
            line = self.view.line(region)
            todo = TodoLine( self.view.substr( line ).rstrip() )
            if not todo.valid :
                continue
            if not todo.priority :
                todo.priority = "E"
            elif todo.priority is not "A":
                todo.priority = PRIORITIES[ PRIORITIES.index( todo.priority ) - 1 ]
            self.view.replace( edit, line, todo.output_line() )


###############################################
class TodosDotTxtDecreasePriority(sublime_plugin.TextCommand):
    def is_enabled( self ):
        return self.view.file_name().endswith( "todo.txt" )
    def run(self, edit):
        for region in self.view.sel():
            line = self.view.line( region )
            todo = TodoLine( self.view.substr( line ).rstrip() )
            if not todo.valid :
                continue
            if todo.priority is "E":
                todo.priority = None
            if todo.priority :
                todo.priority = PRIORITIES[ PRIORITIES.index( todo.priority ) + 1 ]
            self.view.replace( edit, line, todo.output_line() )


###############################################
class TodosDotTxtToggleDone(sublime_plugin.TextCommand):
    def is_enabled( self ):
        return self.view.file_name().endswith( "todo.txt" )
    def run(self, edit):
        for region in self.view.sel():
            line = self.view.line( region )
            todo = TodoLine( self.view.substr( line ).rstrip() )
            if not todo.valid :
                continue
            if todo.creation_date :
                todo.done_date = datetime.date.today()
            todo.done = not todo.done
            self.view.replace( edit, line, todo.output_line() )


###############################################
class TodosDotTxtSort(sublime_plugin.TextCommand):
    def is_enabled( self ):
        return self.view.file_name().endswith( "todo.txt" )
    def run(self, edit):
        todos = []
        non_todos = []
        whole = sublime.Region( 0, self.view.size() )
        lines = self.view.lines( whole )
        for line in lines:
            todo = TodoLine( self.view.substr( line ).rstrip() )
            if not todo.valid :
                print( line )
                non_todos.append( line )
            else:
                todos.append( todo )
        sorted_todos = sorted( todos, key=lambda t: t.priority if t.priority else 'Z' )
        sorted_todos = sorted( sorted_todos, key=attrgetter( 'done' ) )
        output_lines = []
        for t in sorted_todos:
            output_lines.append( t.output_line() )
        output = '\n'.join( output_lines + non_todos )
        self.view.replace( edit, whole, output )


###############################################
class TodosDotTxtAdd(sublime_plugin.TextCommand):
    def is_enabled( self ):
        return get_todofile_path() != None
    def run(self, edit):
        global _edit_instance
        _edit_instance = edit
        def done( text ):
            global _user_input
            global _target
            global _display
            _display = False
            _user_input = text
            view = win.open_file( os.path.expanduser( get_todofile_path() ) )
            if not view.is_loading():
                view.run_command( "todos_txt_add_when_file_open", { "task" : _user_input } )
            else:
                _target = view
        win = self.view.window()
        win.show_input_panel( "Task to add", "", done, lambda x : None, lambda : None )


class TodosTxtAddWhenFileOpen(sublime_plugin.TextCommand):
    def run( self, edit, task ):
        todo = TodoLine( task )
        if todo.valid:
            todo.creation_date = datetime.date.today()
            self.view.insert( edit, 0, todo.output_line() + "\n" )
            self.view.run_command( "todos_txt_sort" )
            self.view.show( self.view.find( todo.output_line(), 0 ) )
        else:
            self.view.insert( edit, 0, task + "\n" )


###############################################
class TodosTxtSearchWhenFileOpen(sublime_plugin.TextCommand):
    def run( self, edit, line ):
        pt = self.view.text_point(line, 0)
        self.view.sel().clear()
        self.view.sel().add( self.view.line( pt ) )
        self.view.show(pt)


class TodosDotTxtSearch( sublime_plugin.TextCommand ):
    def is_enabled( self ):
        return get_todofile_path() != None
    def run( self, edit ):
        win = self.view.window()
        content = None
        with open( os.path.expanduser( get_todofile_path() ), encoding="utf-8", errors="surrogateescape" ) as fh:
            content = fh.read()
        lines = content.split( '\n' )

        sel_lines = []
        sel_linums = []
        ix = 0
        for l in lines:
            if len(l) > 0 and l[0] != 'x':
                sel_lines.append( l )
                sel_linums.append( ix )
            ix += 1

        def done( idx ):
            if idx < 0 :
                return
            global _display
            global _user_input
            global _target
            _display = True
            _user_input = sel_linums[ idx ]
            view = win.open_file( os.path.expanduser( get_todofile_path() ) )
            if not view.is_loading():
                view.run_command( "todos_txt_search_when_file_open", { "task" : _user_input } )
            else:
                _target = view

        self.view.window().show_quick_panel( sel_lines, done )


###############################################
class TodosFileListener(sublime_plugin.EventListener):
    def on_load(self, view):
        global _target
        if _target and view == _target :
            if _display:
                view.run_command( "todos_txt_search_when_file_open", { "line" : _user_input } )
            else:
                view.run_command( "todos_txt_add_when_file_open", { "task" : _user_input } )
            _target = None
