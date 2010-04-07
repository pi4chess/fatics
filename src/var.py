import copy

import trie
import lang

from config import config

vars = trie.Trie()
ivars = trie.Trie()
ivar_number = {}

class BadVarError(Exception):
    pass

class Var(object):
    """This class represents the form of a variable but does not hold
    a specific value.  For example, the server has one global instance of
    this class (actually, a subclass of this class) for the "tell" variable,
    not a separate instance for each user."""
    def __init__(self, name, default):
        assert(name == name.lower())
        self.name = name
        self.default = default
        self.db_store = lambda user_id, name, val: None
        self.is_persistent = False
        # display in vars output
        self.display_in_vars = True

    def hide_in_vars(self):
        self.display_in_vars = False
        return self

    def add_as_var(self): 
        vars[self.name] = self
        self.is_ivar = False
        return self
    
    def add_as_ivar(self, number): 
        ivars[self.name] = self
        ivar_number[number] = self
        self.is_ivar = True
        return self

    def persist(self):
        """Make a variable persistent with the given key in the
        user table."""
        self.is_persistent = True
        return self

    def set(self, user, val):
        """This checks whether the given value for a var is legal and
        sets a user's value of the var.  Returns the message to display to
        the user. On an error, raises BadVarError."""
        pass

class StringVar(Var):
    def __init__(self, name, default, max_len=1023):
        Var.__init__(self, name, default)
        self.max_len = max_len

    def set(self, user, val):
        if val is not None and len(val) > self.max_len:
            raise BadVarError()
        if self.is_ivar:
            user.session.set_ivar(self, val)
        else:
            user.set_var(self, val)
        if val is None:
            user.write(_('''%s unset.\n''') % self.name)
        else:
            user.write((_('''%(name)s set to "%(val)s".\n''') % {'name': self.name, 'val': val}))

    def get_display_str(self, val):
        return '''%s="%s"''' % (self.name, val)

class PromptVar(StringVar):
    def set(self, user, val):
        if val is not None and len(val) > self.max_len - 1:
            raise BadVarError()
        assert(not self.is_ivar)
        if val is None:
            user.set_var(self, val)
            user.write(_('''%s unset.\n''') % self.name)
        else:
            val += ' '
            user.set_var(self, val)
            user.write((_('''%(name)s set to "%(val)s".\n''') % {'name': self.name, 'val': val}))

class LangVar(StringVar):
    def set(self, user, val):
        if val not in lang.langs:
            raise BadVarError()
        if self.is_ivar:
            user.session.set_ivar(self, val)
        else:
            user.set_var(self, val)
        user.write(_('''%(name)s set to "%(val)s".\n''') % {'name': self.name, 'val': val})

class FormulaVar(Var):
    max_len = 1023
    def set(self, user, val):
        if val is not None and len(val) > self.max_len:
            raise BadVarError()
        user.set_formula(self, val)
        if val is None:
            user.write(_('''%s unset.\n''') % self.name)
        else:
            user.write((_('''%(name)s set to "%(val)s".\n''') % {'name': self.name, 'val': val}))

    def get_display_str(self, val):
        return '''%s=%s''' % (self.name, val)

class NoteVar(Var):
    max_len = 1023

    def __init__(self, name, default):
        Var.__init__(self, name, default)
        self.display_in_vars = False # don't display in "vars" output

    def set(self, user, val):
        if val is not None and len(val) > self.max_len:
            raise BadVarError()
        user.set_note(self, val)
        if val is None:
            user.write(_('''Note %s unset.\n''') % self.name)
        else:
            user.write((_('''Note %(name)s set: %(val)s\n''') % {'name': self.name, 'val': val}))

"""An integer variable."""
class IntVar(Var):
    def __init__(self, name, default, min=-99999, max=99999):
        Var.__init__(self, name, default)
        self.min = min
        self.max = max

    def set(self, user, val):
        try:
            val = int(val, 10)
        except ValueError:
            raise BadVarError()
        if val < self.min or val > self.max:
            raise BadVarError()
        if self.is_ivar:
            user.session.set_ivar(self, val)
        else:
            user.set_var(self, val)
        user.write(_("%(name)s set to %(val)s.\n") % {'name': self.name, 'val': val})
    
    def get_display_str(self, val):
        return '''%s=%d''' % (self.name, val)

"""A boolean variable."""
class BoolVar(Var):
    def __init__(self, name, default, on_msg=None, off_msg=None):
        Var.__init__(self, name, default)

        if on_msg is not None:
            self.on_msg = on_msg
        else:
            self.on_msg = N_("%s set.") % name
        if off_msg is not None:
            self.off_msg = off_msg
        else:
            self.off_msg = N_("%s unset.") % name

    def set(self, user, val):
        if val is None:
            # toggle
            if self.is_ivar:
                val = not user.session.ivars[self.name]
            else:
                val = not user.vars[self.name]
        else:
            val = val.lower()
            if val == 'on':
                val = '1'
            elif val == 'off':
                val = '0'
            elif val not in ['0', '1']:
                raise BadVarError()
            val = int(val, 10)
        if self.is_ivar:
            user.session.set_ivar(self, val)
        else:
            user.set_var(self, val)
        if val:
            user.write(_(self.on_msg) + '\n')
        else:
            user.write(_(self.off_msg) + '\n')
    
    def get_display_str(self, val):
        return '''%s=%d''' % (self.name, int(val))

class VarList(object):
    def __init__(self):
        self.init_vars()
        self.init_ivars()

    def init_vars(self):
        BoolVar("shout", True, N_("You will now hear shouts."), N_("You will not hear shouts.")).persist().add_as_var()
        BoolVar("cshout", True, N_("You will now hear cshouts."), N_("You will not hear cshouts.")).persist().add_as_var()
        BoolVar("tell", False, N_("You will now hear direct tells from unregistered users."), N_("You will not hear direct tells from unregistered users.")).persist().add_as_var()
        BoolVar("open", True, N_("You are now open to receive match requests."), N_("You are no longer open to receive match requests.")).persist().add_as_var()
        BoolVar("silence", False, N_("You will now play games in silence."), N_("You will not play games in silence.")).persist().add_as_var()
        BoolVar("bell", True, N_("You will now hear beeps."), N_("You will not hear beeps.")).persist().add_as_var()
        BoolVar("autoflag", True, N_("Auto-flagging enabled."), N_("Auto-flagging disabled.")).persist().add_as_var()
        BoolVar("ptime", False, N_("Your prompt will now show the time."), N_("Your prompt will now not show the time.")).persist().add_as_var()

        IntVar("time", 2, min=0).persist().add_as_var()
        IntVar("inc", 12, min=0).persist().add_as_var()
        IntVar("height", 24, min=5).persist().add_as_var()
        IntVar("width", 79, min=32).persist().add_as_var()

        IntVar("style", 12, min=0, max=12).add_as_var()

        StringVar("interface", None).add_as_var()
        PromptVar("prompt", config.prompt).add_as_var()

        LangVar("lang", "en").persist().add_as_var()

        FormulaVar("formula", None).persist().add_as_var()
        for i in range(1, 10):
            FormulaVar("f%d" % i, None).persist().add_as_var()

        for i in range(1, 11):
            NoteVar(str(i), None).persist().add_as_var()

        self.default_vars = {}
        self.transient_vars = {}
        for var in vars.itervalues():
            if var.is_persistent:
                self.default_vars[var.name] = var.default
            else:
                self.transient_vars[var.name] = var.default

    def init_ivars(self):
        BoolVar("compressmove", False).add_as_ivar(0)
        BoolVar("audiochat", False).add_as_ivar(1)
        BoolVar("seekremove", False).add_as_ivar(2)
        BoolVar("defprompt", False).add_as_ivar(3)
        BoolVar("lock", False).add_as_ivar(4)
        BoolVar("startpos", False).add_as_ivar(5)
        BoolVar("block", False).add_as_ivar(6)
        BoolVar("gameinfo", False).add_as_ivar(7)
        BoolVar("xdr", False).add_as_ivar(8)
        BoolVar("pendinfo", False).add_as_ivar(9)
        BoolVar("graph", False).add_as_ivar(10)
        BoolVar("seekinfo", False).add_as_ivar(11)
        BoolVar("extascii", False).add_as_ivar(12)
        BoolVar("nohighlight", False).add_as_ivar(13)
        BoolVar("highlight", False).add_as_ivar(14)
        BoolVar("showserver", False).add_as_ivar(15)
        BoolVar("pin", False).add_as_ivar(16)
        BoolVar("ms", False).add_as_ivar(17)
        BoolVar("pinginfo", False).add_as_ivar(18)
        BoolVar("boardinfo", False).add_as_ivar(19)
        BoolVar("extuserinfo", False).add_as_ivar(20)
        BoolVar("seekca", False).add_as_ivar(21)
        BoolVar("showownseek", False).add_as_ivar(22)
        BoolVar("premove", False).add_as_ivar(23)
        BoolVar("smartmove", False).add_as_ivar(24)
        BoolVar("movecase", False).add_as_ivar(25)
        BoolVar("suicide", False).add_as_ivar(26)
        BoolVar("crazyhouse", False).add_as_ivar(27)
        BoolVar("losers", False).add_as_ivar(28)
        BoolVar("wildcastle", False).add_as_ivar(29)
        BoolVar("fr", False).add_as_ivar(30)
        BoolVar("nowrap", False).add_as_ivar(31)
        BoolVar("allresults", False).add_as_ivar(32)
        BoolVar("obsping", False).add_as_ivar(33)
        BoolVar("singleboard", False).add_as_ivar(34)

        self.default_ivars = {}
        for ivar in ivars.itervalues():
            self.default_ivars[ivar.name] = ivar.default

    def get_default_vars(self):
        return copy.copy(self.default_vars)

    def get_transient_vars(self):
        return copy.copy(self.transient_vars)
    
    def get_default_ivars(self):
        return copy.copy(self.default_ivars)

varlist = VarList()


'''
ivars:
allresults atomic audiochat
block boardinfo
compressmove crazyhousea
defprompt
extascii extuserinfo
fr
gameinfo graph
lock losers
nohighlight nowrap
pendinfo pin pinginfo premove
seekca seekinfo seekremove showownseek showserver singleboard smartmove startpos suicide
vthighlight
wildcastle
ms ?
xml ?
'''


# vim: expandtab tabstop=4 softtabstop=4 shiftwidth=4 smarttab autoindent
