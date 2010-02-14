import re
import bcrypt
import random
import string

from db import db
import session
from session import Session

class BaseUser:
        def __init__(self):
                self.is_online = False

        def log_in(self, conn):
                self.session = conn.session
                self.session.set_user(self)
                self.is_online = True

        def log_out(self):
                if not self.is_guest:
                        db.user_update_last_logout(self.user.id)
                self.is_online = False

        def write(self, s):
                assert(self.is_online)
                self.session.conn.write(s)
        
        def get_display_name(self):
                if self.is_guest:
                        return self.name + '(U)'
                else:
                        return self.name

# a registered user
class User(BaseUser):
	def __init__(self, u):
                #super(User, self).__init__()
                BaseUser.__init__(self)
                self.id = u['user_id']
                self.name = u['user_name']
                self.passwd_hash = u['user_passwd']
                self.last_logout = u['user_last_logout']
                self.is_guest = False

        def set_passwd(self, passwd):
                self.passwd_hash = bcrypt.hashpw(passwd, bcrypt.gensalt())
                db.set_user_passwd(self.id, self.passwd_hash)

        # test whether a string meets the requirements for a password
        def is_legal_passwd(self, passwd):
                if len(passwd) > 32:
                        return False
                if len(passwd) < 4:
                        return False
                # passwords may not contain spaces because they are set
                # using a command
                if not re.match(r'^\S+$', passwd):
                        return False
                return True
        
        def set_admin_level(self, level):
                db.user_set_admin_level(self.id, level)
        
        # check if an unencrypted password is correct
        def check_passwd(self, passwd):
                # don't perform expensive computation on arbitrarily long data
                if not self.is_legal_passwd(passwd):
                        return False
                return bcrypt.hashpw(passwd, self.passwd_hash) == self.passwd_hash
        
        def get_last_logout(self):
                return db.user_get_last_logout(self.id)

class GuestUser(BaseUser):
        def __init__(self, name):
                #super(GuestUser, self).__init__()
                BaseUser.__init__(self)
                self.is_guest = True
                if name == None:
                        count = 0
                        while True:
                                self.name = 'Guest'
                                for i in range(4):
                                        self.name = self.name + random.choice(string.ascii_uppercase)
                                if not self.name in session.online:
                                        break
                                count = count + 1
                                if count > 3:
                                        raise UsernameException(_('Unable to create a guest account!'))
                                
                        self.autogenerated_name = True
                else:
                        self.name = name
                        self.autogenerated_name = False

class UsernameException(Exception):
        def __init__(self, reason):
                self.reason = reason

class Find:
        # return a user object if one exists; otherwise make a 
        # guest user
        def by_name_for_login(self, name, conn):
                if name.lower() == 'g' or name.lower() == 'guest':
                        u = GuestUser(None)
                        conn.write(_('\nLogging you in as "%s"; you may use this name to play unrated games.\n(After logging in, do "help register" for more info on how to register.)\n\nPress return to enter as "%s":') % (u.name, u.name))
                else:
                        u = self.by_name(name)
                        if u:
                                if u.is_guest:
                                        # It's theoretically possible that
                                        # a new user registers but is blocked
                                        # from logging in by a guest with the
                                        # same name.  We ignore that case.
                                        raise UsernameException(_('Sorry, %s is already logged in. Try again.\n') % name)
                                else:
                                        conn.write(_('\n%s is a registered name.  If it is yours, type the password.\nIf not, just hit return to try another name.\n\npassword: ') % name)
                        else:
                                u = GuestUser(name)
                                conn.write(_('\n"%s" is not a registered name.  You may play unrated games as a guest.\n(After logging in, do "help register" for more info on how to register.)\n\nPress return to enter as "%s":') % (name, name))
                return u

        def by_name(self, name):
                if len(name) < 3:
                        raise UsernameException(_('A name should be at least %d characters long!  Try again.\n') % 3)
                elif len(name) > 18:
                        raise UsernameException(_('Sorry, names may be at most %d characters long.  Try again.\n') % 18)
                elif not re.match('^[a-zA-Z_]+$', name):
                        raise UsernameException(_('Sorry, names can only consist of lower and upper case letters.  Try again.\n'))

                u = self.online(name)
                if not u:
                        dbu = db.get_user(name)
                        if dbu:
                                u = User(dbu)
                        else:
                                u = None
                return u

        def online(self, name):
                name = name.lower()
                if name in session.online:
                        return session.online[name].user
                else:
                        return None

find = Find()

# vim: expandtab tabstop=8 softtabstop=8 shiftwidth=8 smarttab autoindent ft=python
