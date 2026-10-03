"""Public YouTube metadata only. Secrets never enter API responses or cache files."""
import hashlib,json,os,re,threading,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import urlopen
from urllib.error import HTTPError,URLError
LOCK=threading.RLock();CACHE={}

def channel_query(value):
    value=value.strip()
    if re.fullmatch(r'UC[\w-]{22}',value):return {'id':value}
    if value.startswith('https://'):
        url=urlsplit(value)
        if url.hostname not in {'youtube.com','www.youtube.com'}:raise ValueError('Utilisez un identifiant UC…, un @nom ou une URL de chaîne YouTube.')
        value=url.path.strip('/').split('/')[0] if '/@' in url.path else url.path.removeprefix('/channel/').split('/')[0]
    if re.fullmatch(r'@[\w.-]{1,100}',value):return {'forHandle':value[1:]}
    if re.fullmatch(r'UC[\w-]{22}',value):return {'id':value}
    raise ValueError('Utilisez un identifiant UC…, un @nom ou une URL de chaîne YouTube.')

def request(resource,params,key):
    try:
        with urlopen('https://www.googleapis.com/youtube/v3/'+resource+'?'+urlencode({**params,'key':key}),timeout=8) as response:return json.load(response)
    except HTTPError as error:
        raise ValueError('YouTube refuse la requête : vérifiez la clé, ses restrictions et le quota.' if error.code in {400,401,403} else 'YouTube est momentanément indisponible.') from None
    except (URLError,TimeoutError,OSError,ValueError):raise ValueError('Impossible de joindre YouTube. Réessayez plus tard.') from None

def latest(channel,key,force=False,fetcher=request,clock=time.time):
    if not key:raise ValueError('Ajoutez une clé YouTube Data API v3 pour configurer cette source.')
    query=channel_query(channel);identity=hashlib.sha256((channel+'\0'+key).encode()).hexdigest()
    with LOCK:
        cached=CACHE.get(identity);now=clock()
        if not force and cached and now-cached[0]<300:return {**cached[1],'cached':True}
        try:
            channels=fetcher('channels',{'part':'snippet,contentDetails',**query},key).get('items',[])
            if not channels:raise ValueError('Chaîne YouTube introuvable.')
            item=channels[0];playlist=item.get('contentDetails',{}).get('relatedPlaylists',{}).get('uploads')
            if not playlist:raise ValueError('La playlist des vidéos de cette chaîne est indisponible.')
            uploads=fetcher('playlistItems',{'part':'contentDetails','playlistId':playlist,'maxResults':50},key).get('items',[])
            ids=[i.get('contentDetails',{}).get('videoId','') for i in uploads];ids=[i for i in ids if re.fullmatch(r'[\w-]{11}',i)]
            videos=fetcher('videos',{'part':'snippet,status','id':','.join(ids),'maxResults':50},key).get('items',[]) if ids else []
            public=[]
            for video in videos:
                snippet=video.get('snippet',{});published=snippet.get('publishedAt','')
                try:stamp=datetime.fromisoformat(published.replace('Z','+00:00')).timestamp()
                except (ValueError,TypeError):continue
                if not re.fullmatch(r'[\w-]{11}',video.get('id','')) or video.get('status',{}).get('privacyStatus')!='public' or snippet.get('liveBroadcastContent')=='upcoming' or stamp>now:continue
                public.append((stamp,video))
            result=None
            if public:
                _,video=max(public,key=lambda pair:pair[0]);snippet=video['snippet'];thumb=snippet.get('thumbnails',{})
                thumbnail=next((thumb[size].get('url') for size in ['maxres','standard','high','medium','default'] if size in thumb),None)
                result={'title':snippet.get('title') or 'Vidéo YouTube','url':'https://www.youtube.com/watch?v='+video['id'],'published':snippet['publishedAt']}
                if isinstance(thumbnail,str) and urlsplit(thumbnail).scheme=='https' and urlsplit(thumbnail).hostname=='i.ytimg.com':result['thumbnail']=thumbnail
            data={'channel_id':item['id'],'channel_name':item.get('snippet',{}).get('title',item['id']),'video':result,'cached':False}
            CACHE[identity]=(now,data);return data
        except ValueError:
            if not force and cached and now-cached[0]<3600:return {**cached[1],'cached':True,'stale':True}
            raise

def key_path(directory):return Path(directory)/'youtube-api-key'
def read_key(directory):
    if os.environ.get('YOUTUBE_API_KEY'):return os.environ['YOUTUBE_API_KEY'].strip()
    try:return key_path(directory).read_text().strip()
    except FileNotFoundError:return ''
def store_key(directory,value):
    if os.environ.get('YOUTUBE_API_KEY'):raise ValueError('La clé est gérée par la configuration serveur.')
    if not isinstance(value,str) or (value and not re.fullmatch(r'[A-Za-z0-9_-]{20,200}',value)):raise ValueError('Clé API invalide.')
    target=key_path(directory)
    if not value:target.unlink(missing_ok=True);return
    temporary=target.with_suffix('.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(value)
    temporary.replace(target)
