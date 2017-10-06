# Copyright [yyyy] [name of copyright owner]
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os.path
import os
import time
import socket
import subprocess
import StringIO
import csv
import struct

import logging

try:
    config_file = os.environ["TWNM_CONFIG"]
except KeyError:
    config_file = "/etc/twnm/uplink/uplink.json"

def get_dict(d, key, default):
    try:
        v = d[key]
    except KeyError:
        return default
    if isinstance(v, unicode):
        return v.encode("utf-8")
    else:
        return v

def netmask_bits(netmask):
    addr = struct.unpack("!L", socket.inet_aton(netmask))[0]
    bits = 0
    while addr != 0 and addr & 1 == 0:
        addr = addr >> 1
        bits += 1
    return 32-bits

def ip_link_down(device):
    logging.info("ip link down: %s", device)
    exitcode = subprocess.call(["/sbin/ip", "link", "set", "dev", device, "down"])
    if exitcode != 0:
        raise ValueError("Cannot bring %s down (exit code: %d)" % (device, exitcode))

def ip_link_up(device):        
    logging.info("ip link up: %s", device)
    exitcode = subprocess.call(["/sbin/ip", "link", "set", "dev", device, "up"])
    if exitcode != 0:
        raise ValueError("Cannot bring %s up (exit code: %d)" % (device, exitcode))

def ip_link_up_addr(device, ipv4, netmask, gateway, dns):
    logging.info("ip link up: %s addr=%s/%s gw=%s dns=%s", device, ipv4, netmask, gateway, dns)        
    exitcode = subprocess.call(["/sbin/ip", "link", "set", "dev", device, "up"])
    if exitcode != 0:
        raise ValueError("Cannot bring %s up (exit code: %d)" % (device, exitcode))
    exitcode = subprocess.call(["/sbin/ip", "address", "add", "%s/%d" % (ipv4, netmask_bits(netmask)),
        "dev", device])
    if exitcode != 0:
        raise ValueError("Cannot assign address to %s (exit code: %d)" % (device, exitcode))
    exitcode = subprocess.call(["/sbin/ip", "route", "replace", "to", "default", "via", gateway, "dev", device])
    if exitcode != 0:
        raise ValueError("Cannot change route table for %s (exit code: %d)" % (device, exitcode))
    
    p = subprocess.Popen(["/sbin/resolvconf", "-a", "%s.twnm" % device], stdin=subprocess.PIPE)
    p.communicate(input="nameserver %s\n" % dns)
    exitcode = p.poll()

    if exitcode != 0:
        raise ValueError("Cannot configure DNS for %s (exit code: %d)" % (device, exitcode))

def dhclient_pid(device):
    return os.path.join("/run", "dhclient.%s.pid" % device)

def dhclient_leases(device):
    return os.path.join("/run", "dhclient.%s.leases" % device)

def dhclient_6leases(device):
    return os.path.join("/run", "dhclient6.%s.leases" % device)

def start_dhclient(device):
    logging.info("Starting dhclient for %s", device)
    p = subprocess.Popen(["/sbin/dhclient", "-1", "-pf", dhclient_pid(device), 
        "-lf", dhclient_leases(device), "-I", "-df", dhclient_6leases(device), device])
    timeout = 30 # wait 30 secs
    while timeout > 0:
        exitcode = p.poll()
        if exitcode is not None:
            break
        timeout -= 1
        time.sleep(1)
    if exitcode is None:
        try:
            p.kill()
        except:
            pass
        raise ValueError("Could not get DHCP lease for device %s" % device)

def stop_dhclient(device):
    logging.info("Stopping dhclient for %s", device)
    exitcode = subprocess.call(["/sbin/dhclient", "-x", "-pf", dhclient_pid(device)])       

def wpa_supplicant_update(device, ssid, psk):
    logging.info("Updating wpa_supplicant for dev %s ssid %s", device, ssid)
    p = subprocess.Popen(["/sbin/wpa_cli", "-i", device, "list_networks"], stdout=subprocess.PIPE)
    stdout, stderr = p.communicate()
    exitcode = p.poll()
    if exitcode != 0:
        raise ValueError("Cannot list WiFi networks for %s (exit code: %d)" % (device, exitcode))
    first = True
    networks = {}
    for r in csv.reader(stdout.splitlines(), delimiter='\t'):
        if first:
            first = False
        else:
            id = str(r[0])
            _ssid = str(r[1])
            networks[_ssid] = id

    if ssid in networks:
        nid = networks[ssid]
        logging.info("wpa_supplicant_update: updating existing network: %s -- %s", ssid, nid)
    else:
        logging.info("wpa_supplicant_update: wpa_cli -i %s add_network", device)
        p = subprocess.Popen(["/sbin/wpa_cli", "-i", device, "add_network"], stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        exitcode = p.poll()
        if exitcode != 0:
            raise ValueError("Cannot add a WiFi network for %s (exit code: %d)" % (device, exitcode))
        nid = stdout.rstrip()

    logging.info("wpa_supplicant_update: wpa_cli -i %s set_network %s ssid \\\"%s\\\"", device, nid, ssid)
    exitcode = subprocess.call(["/sbin/wpa_cli", "-i", device, "set_network", nid, "ssid", "\"%s\""%ssid])
    if exitcode != 0:
        raise ValueError("Cannot set a WiFi network SSID for %s (exit code: %d)" % (device, exitcode))
    logging.info("wpa_supplicant_update: wpa_cli -i %s set_network %s psk \\\"%s\\\"", device, nid, "****")
    exitcode = subprocess.call(["/sbin/wpa_cli", "-i", device, "set_network", nid, "psk", "\"%s\""%psk])
    if exitcode != 0:
        raise ValueError("Cannot set a WiFi network PSK for %s (exit code: %d)" % (device, exitcode))
    logging.info("wpa_supplicant_update: wpa_cli -i %s select_network %s", device, nid)
    exitcode = subprocess.call(["/sbin/wpa_cli", "-i", device, "select_network", nid])
    if exitcode != 0:
        raise ValueError("Cannot set a WiFi network PSK for %s (exit code: %d)" % (device, exitcode))
    

def update_interfaces(config_file):
    logging.info("Prepare to update interfaces")
    with open(config_file) as f:
        config = json.load(f)

    wired = get_dict(config, "wired", None)
    wifi = get_dict(config, "wifi", None)
    cellular = get_dict(config, "cellular", None)
    if wired:
        device = get_dict(wired, "device", None)
        if device is None:
            raise ValueError("wired: device not specified")
        if get_dict(wired, "enabled", False):
            logging.info("Wired configuration present and ENABLED")
            dhcp = get_dict(wired, "dhcp", False)
            ipv4 = get_dict(wired, "ipv4", "")
            netmask = get_dict(wired, "netmask", "")
            gateway = get_dict(wired, "gateway", "")
            dns = get_dict(wired, "dns", "8.8.8.8")

            if dhcp:
                logging.info("wired: using DHCP")
                ip_link_down(device)
                ip_link_up(device)
                start_dhclient(device)
            else:
                logging.info("wired: using static config")
                if not ipv4:
                    raise ValueError("wired: static IPv4 config: address not specified")
                if not netmask:
                    raise ValueError("wired: static IPv4 config: netmask not specified")
                if not gateway:
                    raise ValueError("wired: static IPv4 config: gateway not specified")
                
                try:
                    socket.inet_aton(ipv4)
                except:
                    raise ValueError("wired: static IPv4 config: invalid IPv4 address: %s" % ipv4)
                try:
                    socket.inet_aton(netmask)
                except:
                    raise ValueError("wired: static IPv4 config: invalid IPv4 netmask: %s" % netmask)
                try:
                    socket.inet_aton(gateway)
                except:
                    raise ValueError("wired: static IPv4 config: invalid IPv4 gateway: %s" % gateway)

                ip_link_down(device)
                stop_dhclient(device)
                ip_link_up_addr(device, ipv4, netmask, gateway, dns)
        
            if wifi and get_dict(wifi, "device", None):
                device = get_dict(wifi, "device", None)
                ip_link_down(device)            
                stop_dhclient(device)
            if cellular and get_dict(cellular, "device", None):
                device = get_dict(cellular, "device", None)
                ip_link_down(device)            
                stop_dhclient(device)

            return

        else:
            ip_link_down(device)
            stop_dhclient(device)

    if wifi:
        device = get_dict(wifi, "device", None)
        if device is None:
            raise ValueError("wifi: device not specified")
        if get_dict(wifi, "enabled", False):
            logging.info("WiFi configuration present and ENABLED")

            ssid = get_dict(wifi, "ssid", None)
            psk = get_dict(wifi, "psk", None)

            if ssid is None:
                raise ValueError("wifi: SSID of the network to connect not specified")
            
            wpa_supplicant_update(device, ssid, psk)
            ip_link_down(device)
            ip_link_up(device)
            start_dhclient(device)

            if cellular and get_dict(cellular, "device", None):
                device = get_dict(cellular, "device", None)
                ip_link_down(device)            
                stop_dhclient(device)

            return

        else:
            ip_link_down(device)
            stop_dhclient(device)

    if cellular:
        device = get_dict(cellular, "device", None)
        if device is None:
            raise ValueError("cellular: device not specified")
        if get_dict(cellular, "enabled", False):
            logging.info("Cellular configuration present and ENABLED")

            # TODO configure cellular
            pass
        
            return
        else:
            ip_link_down(device)
            stop_dhclient(device)
    

def main():
    logging.info("Starting TW NetworkManager")
    last_update = 0
    while True:
        if os.path.isfile(config_file):
            mtime = os.path.getmtime(config_file)
            if mtime != last_update:
                logging.info("%s has been found and has newer modification timestamp (%d)", config_file, mtime)
                try:
                    update_interfaces(config_file)
                except:
                    logging.error("Error updating network interfaces", exc_info=True)
                last_update = mtime
        time.sleep(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
