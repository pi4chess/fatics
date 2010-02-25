import re
import bcrypt
import random
import string

import admin
from db import db
import session
from online import online
import var
import channel

class UsernameException(Exception):
        def __init__(self, reason):
                self.reason = reason

class BaseUser(object):
        def __init__(self):
                self.is_online = False

        def log_on(self, conn):
                if not self.is_guest:
                        if online.is_online(self.name):
                                conn.write(_("**** %s is already logged in; closing the other connection. ****\n" % self.name))
                                u = online.find_exact(self.name)
                                u.session.conn.write(_("**** %s has arrived; you can't both be logged in. ****\n\n") % self.name)
                                #u.session.conn.write(_("**** %s has arrived - you can't both be logged in. ****\n\n") % self.name)
                                u.session.conn.loseConnection('logged in again')
                        count = 0
                        while online.is_online(self.name):
                                time.sleep(0.1)
                                count += 1
                                if count > 50:
                                        raise Exception("failed to kick off user")
                self.is_online = True
                self.aliases = {}
                self.session = conn.session
                self.session.set_user(self)
                online.add(self)
                for ch in self.channels:
                        channel.chlist[ch].log_on(self)
                conn.write(_('**** Starting session as %s ****\n\n') % self.name)

        def log_off(self):
                for ch in self.channels:
                        channel.chlist[ch].log_off(self)
                self.is_online = False
                online.remove(self)

        def write(self, s):
                assert(self.is_online)
                self.session.conn.write(s)
        
        def write_prompt(self, s):
                assert(self.is_online)
                self.session.conn.write(s)
                self.session.conn.write('fics% ')
        
        def get_display_name(self):
                ret = self.name
                if self.admin_level >= admin.Level.admin:
                         ret += '(*)'
                if self.is_guest:
                        ret += '(U)'
                return ret

        def set_var(self, v, val):
                self.vars[v.name] = val

        def add_channel(self, id):
                assert(type(id) == type(1) or type(id) == type(1l))
                self.channels.append(id)
        
        def remove_channel(self, id):
                assert(type(id) == type(1) or type(id) == type(1l))
                self.channels.remove(id)
                
        def set_admin_level(self, level):
                self.admin_level = level


# a registered user
class User(BaseUser):
	def __init__(self, u):
                BaseUser.__init__(self)
                self.id = u['user_id']
                self.name = u['user_name']
                self.passwd_hash = u['user_passwd']
                self.last_logout = u['user_last_logout']
                self.admin_level = u['user_admin_level']
                self.is_guest = False
                self.vars = db.user_load_vars(self.id)
                self.channels = db.user_get_channels(self.id)
               
        def log_off(self):
                BaseUser.log_off(self)
                db.user_set_last_logout(self.id)

        def set_passwd(self, passwd):
                self.passwd_hash = bcrypt.hashpw(passwd, bcrypt.gensalt())
                db.user_set_passwd(self.id, self.passwd_hash)

        def set_admin_level(self, level):
                BaseUser.set_admin_level(self, level)
                db.user_set_admin_level(self.id, level)
        
        # check if an unencrypted password is correct
        def check_passwd(self, passwd):
                # don't perform expensive computation on arbitrarily long data
                if not is_legal_passwd(passwd):
                        return False
                return bcrypt.hashpw(passwd, self.passwd_hash) == self.passwd_hash
        
        def get_last_logout(self):
                return db.user_get_last_logout(self.id)
        
        def remove(self):
                return db.user_delete(self.id)
        
        def set_var(self, v, val):
                BaseUser.set_var(self, v, val)
                db.user_set_var(self.id, v.name, val)
        
        def add_channel(self, id):
                BaseUser.add_channel(self, id)
                db.channel_add_user(id, self.id)
        
        def remove_channel(self, id):
                BaseUser.remove_channel(self, id)
                db.channel_del_user(id, self.id)

class GuestUser(BaseUser):
        def __init__(self, name):
                BaseUser.__init__(self)
                self.is_guest = True
                if name == None:
                        count = 0
                        while True:
                                self.name = 'Guest'
                                for i in range(4):
                                        self.name = self.name + random.choice(string.ascii_uppercase)
                                if not session.online.is_online(self.name):
                                        break
                                count = count + 1
                                if count > 3:
                                        raise UsernameException(_('Unable to create a guest account!'))
                                
                        self.autogenerated_name = True
                else:
                        self.name = name
                        self.autogenerated_name = False
                self.admin_level = admin.Level.user
                self.vars = var.varlist.get_default_vars()
                self.channels = channel.chlist.get_default_guest_channels()

class AmbiguousException(Exception):
        def __init__(self, names):
                self.names = names

class Find(object):
        def by_name_exact(self, name, min_len = 3):
                if len(name) < min_len:
                        raise UsernameException(_('A name should be at least %d characters long!  Try again.\n') % 3)
                elif len(name) > 18:
                        raise UsernameException(_('Sorry, names may be at most %d characters long.  Try again.\n') % 18)
                elif not re.match('^[a-zA-Z_]+$', name):
                        raise UsernameException(_('Sorry, names can only consist of lower and upper case letters.  Try again.\n'))

                u = session.online.find_exact(name)
                if not u:
                        dbu = db.user_get(name)
                        if dbu:
                                u = User(dbu)
                return u

        """ find a user but allow the name to abbreviated if
        it is unambiguous; if the name is not an exact match, prefer
        online users to offline """
        def by_name_or_prefix(self, name):
                u = None
                if len(name) >= 2:
                        u = self.by_name_exact(name, 2)
                if not u:
                        ulist = session.online.find_matching(name)
                        if len(ulist) == 1:
                                u = ulist[0]
                        elif len(ulist) > 1:
                                # when there are multiple matching users
                                # online, don't bother searching for offline
                                # users who also match
                                raise AmbiguousException([u.name for u in ulist])
                if not u: 
                        ulist = db.user_get_matching(name)
                        if len(ulist) == 1:
                                u = User(ulist[0])
                        elif len(ulist) > 1:
                                raise AmbiguousException([u['user_name'] for u in ulist])
                return u

find = Find()
        
# test whether a string meets the requirements for a password
def is_legal_passwd(passwd):
        if len(passwd) > 32:
                return False
        if len(passwd) < 4:
                return False
        # passwords may not contain spaces because they are set
        # using a command
        if not re.match(r'^\S+$', passwd):
                return False
        return True

class Create(object):
        def passwd(self):
                chars = string.letters + string.digits
                passlen = random.choice(range(5, 8))
                ret = ''
                for i in range(passlen):
                        ret = ret + random.choice(chars)
                return ret

        def new(self, name, email, passwd, real_name):
                hash = bcrypt.hashpw(passwd, bcrypt.gensalt())
                db.user_add(name, email, hash, real_name, admin.Level.user)
create = Create()

# vim: expandtab tabstop=8 softtabstop=8 shiftwidth=8 smarttab autoindent ft=python