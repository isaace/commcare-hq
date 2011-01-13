#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import json

import logging
from datetime import datetime
import re
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from corehq.apps.sms.util import send_sms
from corehq.apps.users.models import CouchUser, PhoneUser
from corehq.apps.sms.models import MessageLog, INCOMING
from corehq.apps.groups.models import Group
from corehq.util.webutils import render_to_response
from . import util
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.couch.database import get_db


def messaging(request, domain, template="sms/default.html"):
    context = {}
    if request.method == "POST":
        if ('userrecipients[]' not in request.POST and 'grouprecipients[]' not in request.POST) \
          or 'text' not in request.POST:
            context['errors'] = "Error: must select at least 1 recipient and write a message."
        else:
            num_errors = 0
            text = request.POST["text"]
            if 'userrecipients[]' in request.POST:
                phone_numbers = request.POST.getlist('userrecipients[]')
                for phone_number in phone_numbers:
                    id, phone_number = phone_number.split('_')
                    success = util.send_sms(domain, id, phone_number, text)
                    if not success:
                        num_errors = num_errors + 1
            else:            
                groups = request.POST.getlist('grouprecipients[]')
                for group_id in groups:
                    group = Group.get(group_id)
                    users = CouchUser.view("users/by_group", key=[domain, group.name], include_docs=True).all()
                    #user_ids = [m['value'] for m in CouchUser.view("users/by_group", key=[domain, group.name]).all()]
                    #users = [m for m in CouchUser.view("users/all_users", keys=user_ids).all()]
                    users = [m['doc'] for m in users]
                    for user in users: 
                        success = util.send_sms(domain, 
                                                user.get_id, 
                                                user.default_phone_number(), 
                                                text)
                        if not success:
                            num_errors = num_errors + 1
            if num_errors > 0:
                context['errors'] = "Could not send %s messages" % num_errors
            else:
                return HttpResponseRedirect( reverse("messaging", kwargs={ "domain": domain} ) )
    phone_users = PhoneUser.view("users/phone_users_by_domain", key=domain)
    groups = Group.view("groups/by_domain", key=domain)
    context['domain'] = domain
    context['phone_users'] = phone_users
    context['groups'] = groups
    context['messagelog'] = MessageLog.objects.filter(domain=domain)
    return render_to_response(request, template, context)

def post(request, domain):
    """
    We assume sms sent to HQ will come in the form
    http://hqurl.com?username=%(username)s&password=%(password)s&id=%(phone_number)s&text=%(message)s
    """
    text = request.REQUEST.get('text', '')
    to = request.REQUEST.get('id', '')
    username = request.REQUEST.get('username', '')
    # ah, plaintext passwords....  
    # this seems to be the most common API that a lot of SMS gateways expose
    password = request.REQUEST.get('password', '')
    if not text or not to or not username or not password:
        error_msg = 'ERROR missing parameters. Received: %(1)s, %(2)s, %(3)s, %(4)s' % \
                     ( text, to, username, password )
        logging.error(error_msg)
        return HttpResponseBadRequest(error_msg)
    user = authenticate(username=username, password=password)
    if user is None or not user.is_active:
        return HttpResponseBadRequest("Authentication fail")
    msg = MessageLog(domain=domain,
                     # how to map phone numbers to recipients, when phone numbers are shared?
                     #couch_recipient=id, 
                     phone_number=to,
                     direction=INCOMING,
                     date = datetime.now(),
                     text = text)
    msg.save()
    return HttpResponse('OK')     


def get_sms_autocomplete_context(request, domain):
    """A helper view for sms autocomplete"""
    phone_users = PhoneUser.view("users/phone_users_by_domain", key=domain)
    groups = Group.view("groups/by_domain", key=domain)

    contacts = []
    contacts.extend(['%s (group)' % group.name for group in groups])
    contacts.extend(['"%s" <%s>' % (user.name, user.phone_number) for user in phone_users])
    return {"sms_contacts": json.dumps(contacts)}

@login_and_domain_required
def send_to_recipients(request, domain):
    recipients = request.POST.get('recipients')
    message = request.POST.get('message')
    recipients = [x.strip() for x in recipients.split(',') if x.strip()]
    phone_numbers = []
    # formats: GroupName (group), "Username" <+15555555555>, +15555555555
    group_names = []
    usernames = []
    phone_numbers = []
    for recipient in recipients:
        if recipient.endswith("(group)"):
            name = recipient.strip("(group)").strip()
            group_names.append(name)
        elif re.match(r'"[\w\.]+" <\d+>', recipient):
            name = recipient.split('"')[1]
            usernames.append(name)
        elif re.match(r'\+\d+', recipient):
            phone_numbers.append(recipient)
            

    users = get_db().view('users/by_group', keys=[[domain, gn] for gn in group_names], include_docs=True).all()
    users.extend(get_db().view('users/by_username', keys=[[domain, un] for un in usernames], include_docs=True).all())
    phone_numbers.extend([r['doc']['phone_numbers'][-1]['number'] for r in users])

    for number in phone_numbers:
        send_sms(domain, "", number, message)
    return HttpResponse(json.dumps({"phone_numbers": phone_numbers, "message": message}))
