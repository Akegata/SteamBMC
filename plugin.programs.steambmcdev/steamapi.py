import requests
import xml.sax
import os, sys, time, random
import os.path
import xbmc, xbmcaddon
from PIL import Image

# Import appropriate apputils
if sys.platform.startswith("win"):
    import winutils as _coreapputils
else:
    raise RuntimeError, "platform `%s' not yet supported... sorry!" % sys.platform


addon = xbmcaddon.Addon()
addon_name = addon.getAddonInfo('name')
lang = addon.getLocalizedString

USERDATA_FOLDER = xbmc.translatePath(os.path.join("special://masterprofile", "addon_data", addon_name))
ARTWORK_CACHE_FOLDER = os.path.join(USERDATA_FOLDER, "artworkcache")
STEAM_BIN = addon.getSetting("steam_bin")

XBMC_WIDEBANNERSIZE = (758, 140)
XBMC_TALLICONSIZE = (256, 256)

"""
startSteam:     Start Steam in the background if it is not already running.

TODO: Add support for auto log in.
"""
def startSteam():
    _coreapputils.launchFork("\"%s\" -silent" % STEAM_BIN.replace('"', '\"'))

"""
getValveCdn:    Return a random cdn number for steampowered.com

@return         (string) Single character, currently between 2 and 3, unless Valve adds
                more or changes CDN numbering.
"""
def getValveCdn():
    return str(random.randrange(2, 3))


class SteamGameInfoParser(xml.sax.ContentHandler):
    """
    SteamGameInfoParser:    SAX parsing engine for Steam user game info (XML)
    """
    state = 0
    data = ""
    games = []
    
    def characters(self, data):
        self.data += data
    
    def startElement(self, name, attrs):
        if name == "game":
            self.state = 1 # begin listening
            self.games.append({})
            self.data = ""
    
    def endElement(self, name):
        # Are we reading game info?
        if self.state == 1:
            # Add the attribute
            self.games[-1][name] = self.data
            self.data = ""


class SteamGame(object):
    """
    __init__: Create the steam game with all necessary parameters.

    @param         game_id                Steams unique id for the game.

    @param         game_name              Name of the game.
    """
    def __init__(self, game_id, game_name):
        self.game_id = game_id
        self.game_name = game_name
        self.game_logo = ""
        # Steam Community stats only
        self.hours_played = 0.0
        self.hours_played_last2weeks = 0.0
        # Artwork
        self.artwork_promo = []
        self.artwork_logo = []
        self.artwork_logo_url = ""

    """
    setPlayTime: Set the playtime stats.

    @param          hours_played        (optional) Total hours played, defaults to 0.0.

    @param          hours_played_2wk    (optional) Hours played in last two weeks, defaults to 0.0.
    """
    def setPlayTime(self, hours_played=0.0, hours_played_last2weeks=0.0):
        self.hours_played = hours_played
        self.hours_played_last2weeks = hours_played_last2weeks

    """
    scrapeLogos: Scrapes the game logos, which are used as icons of the ListItem.

    @param          session: The requests.Session() in which the get requests are executed.

    @param          artupdate: Whether the art (logos and fanart) should be updated or not.

    @return         The file path to the logo in png format.
    """
    def scrapeLogos(self, session=None, artupdate=False):
        xbmc.log("Checking artwork for #%d" % self.game_id, xbmc.LOGDEBUG)
        file_path = os.path.join(ARTWORK_CACHE_FOLDER, "game_%d_logo_1.jpg" % (self.game_id))
        file_path_png = os.path.join(ARTWORK_CACHE_FOLDER, "game_%d_logo_1.png" % (self.game_id))

        if os.path.isfile(file_path_png) or not artupdate:
            self.artwork_logo = [file_path_png]
            return
        if artupdate:
            try:
                os.remove(file_path_png)
            except IOError:
                # Ignore.

        #url = 'http://cdn' + getValveCdn() + '.steampowered.com/v/gfx/apps/' + str(self.game_id) + '/header.jpg'
        try:
            if session != None:
                r = session.get(game.artwork_logo_url, stream=True)
            else:
                r = requests.get(game.artwork_logo_url, stream=True)
        except requests.exceptions.ConnectionError as e:
            # Use Default Thumbnail.
            xbmc.log("Artwork Scraping Error: " + e, xbmc.LOGDEBUG)
            return
        with open(file_path, "wb") as file:
            for chunk in r.iter_content():
                file.write(chunk)

        # Save as .png
        try:
            Image.open(file_path).save(file_path_png)
        except IOError:
            img = Image.new("RGB", (460, 215), "black")
            img.save(file_path_png)
            self.artwork_logo = [file_path_png]
            return file_path_png

        os.remove(file_path)
        self.artwork_logo = [file_path_png]
        return file_path_png

    """
    launchGame: Launch this game using Steam. Takes account of platform.

    @return     True if believed successful, False if not
    """
    def launchGame(self):
        _coreapputils.launchFork("\"%s\" -applaunch %d" % (STEAM_BIN.replace('"', '\"'), self.game_id))
        time.sleep(5) # Give Steam a few seconds to start.
        if os.path.basename(STEAM_BIN) not in _coreapputils.getProcessesList():
            return False
        return True


class SteamUser(object):
    """
    __init__: Create the steam user interface.
    
    @param      public_name     Public name is set up in the Steam profile and 
                                can be the same as the Steam user's name or to
                                whatever they like, but it must be unique and
                                present.
    """
    def __init__(self, public_name):
        assert len(public_name) != 0
        self._public_name = public_name
        self.owned_games = []
        self.exception = None

    """
    getOwnedGames: Creates the list of games owned by the user.

    @param              prog_callback: xbmcgui.ProgressDialog to update progress
                        status during the data fetch.

    @param              artupdate: Whether the art (logos and fanart) should be updated or not.

    @param              getart: Whether art should be fetched or not.
    
    @return             The list of owned games.
    """
    def getOwnedGames(self, prog_callback=None, artupdate=False, getart=True):
        # If the community isn't available, raise an exception.
        try:
            r = requests.get('http://steamcommunity.com/id/' + self._public_name + '/games?tab=all&xml=1', timeout=10)
        except requests.exceptions.ConnectionError as e:
            self.exception = e
            raise RuntimeError, "Can't connect to SteamCommunity.com for games list"
        if r.content == None:
            self.exception = "No data received"
            raise RuntimeError, "Can't connect to SteamCommunity.com for games list"
        
        sax_engine = SteamGameInfoParser()
        xml.sax.parseString(r.content, sax_engine)
        num_games = len(sax_engine.games)
        num = 0
        s = requests.Session()
        for game_info in sax_engine.games:
            if hasattr(prog_callback, "update"):
                # We don't get here with zero games, so we're not worried about a divide by zero error.
                prog_callback.update(15 + int((float(num) / float(num_games)) * 85), lang(33014) % game_info['name'].strip())
                if prog_callback.iscanceled():
                    # If cancelled abort fetch of all games so we don't get an inconsistent list
                    self.owned_games = []
                    break

            game = SteamGame(int(game_info['appID']), game_info['name'].strip().encode('UTF-8'))
            game.artwork_logo_url = game_info['logo'].strip().encode('UTF-8')
            if getart:
                game.scrapeLogos(s, artupdate)
            if 'hoursLast2Weeks' in game_info and 'hoursOnRecord' in game_info:
                game.setPlayTime(float(game_info['hoursLast2Weeks']), float(game_info['hoursOnRecord']))
            self.owned_games.append(game)
            num += 1
        
        return self.owned_games

    """
    getInstalledGames: returns all games which are installed on the users computer.

    @return             An array containing the AppIDs of the games.
    """
    def getInstalledGames(self):
        steamapps = STEAM_BIN[:-10]
        dir = os.listdir(steamapps + "\SteamApps")
        games = []
        for file in dir:
            if file.startswith("appmanifest_"):
                games.append(file[12:-4])
        return games