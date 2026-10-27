# Pixeline i browseren (Unraid-app)

Kører de gamle Pixeline-spil i browseren på iPad og pc. Bag det ligger en rettet udgave af
[DirPlayer](https://github.com/igorlira/dirplayer-rs) (GPL-3), som afspiller Director-filer.

Imaget indeholder **ingen spilfiler**. Du lægger dine egne ISO-filer i en mappe på Unraid, og
containeren gør dem klar første gang, den starter. Originalerne bliver aldrig ændret.

Status: Kun "Syng, leg og lær" er testet og kan spilles med lyd. De andre spil bliver også
klargjort og vist på listen, men de er ikke afprøvet endnu.

- Repo: http://192.168.68.58:3333/kim/pixeline-web
- Image: `192.168.68.58:3333/kim/pixeline-web:latest` (Giteas pakke-register)

Alle kommandoer herunder køres i Unraid-terminalen (ikonet `>_` øverst til højre).

## 1. Én gang: lad Docker hente fra Gitea over http

Gitea kører på `http://`, så Docker skal have lov til at bruge registeret uden https. Gå til
**Settings → Docker**, sæt **Enable Docker** til *No* og tryk Apply. Kør derefter:

```bash
echo 'DOCKER_OPTS="--insecure-registry=192.168.68.58:3333"' >> /boot/config/docker.cfg
```

Sæt **Enable Docker** tilbage til *Yes*. Indstillingen bliver liggende efter genstart.

## 2. Byg imaget og læg det i Gitea

Log ind på registeret med dit Gitea-brugernavn og et adgangstoken med rettigheden
`write:package`. Tokenet laver du i Gitea under *Indstillinger → Applikationer*.

```bash
docker login 192.168.68.58:3333
```

Byg imaget direkte fra repoet, og push det:

```bash
docker build -t 192.168.68.58:3333/kim/pixeline-web:latest http://192.168.68.58:3333/kim/pixeline-web.git#main && docker push 192.168.68.58:3333/kim/pixeline-web:latest
```

Kør de samme to kommandoer igen, når der er kommet en ny udgave i repoet. Har du senere en
Gitea Actions-runner, gør `.gitea/workflows/build.yml` det automatisk ved hvert push. Den
skal have en repository-secret `REGISTRY_TOKEN` med samme slags token.

## 3. Tilføj templaten

```bash
wget -O /boot/config/plugins/dockerMan/templates-user/my-pixeline.xml http://192.168.68.58:3333/kim/pixeline-web/raw/branch/main/unraid/pixeline.xml
```

Gå til **Docker → Add Container**, og vælg **pixeline** under *Template*. Tjek de to stier:

| Felt | Standard |
|---|---|
| ISO-mappe | `/mnt/user/isos/pixeline`: læg dine Pixeline ISO-filer her |
| Spildata | `/mnt/user/appdata/pixeline` |
| WebUI | port `8080` |

Tryk **Apply**. Herefter ligger appen på Docker-fanen med ikon og WebUI-knap ligesom en
app fra Community Apps. **Check for updates** og **Update** virker også, når du har pushet et
nyt image.

Bemærk: Templaten og ikonet hentes uden login. Hvis repoet er privat, så kopiér
`unraid/pixeline.xml` manuelt til `/boot/config/plugins/dockerMan/templates-user/`.

Første start tager et minuts tid pr. spil, mens ISO'erne pakkes ud. Følg med i containerens
log eller på forsiden.

## 4. Spil på iPad

1. Åbn `http://<unraid-ip>:8080` i Safari.
2. Tryk på dele-knappen og vælg **Føj til hjemmeskærm**. Så åbner spillet i fuld skærm som en app.
3. Vend iPad'en på langs og tryk **Tryk for at starte**. Det tryk er nødvendigt, for ellers
   tillader iOS ikke lyd.

## Nye spil

- **Nyt spil:** læg ISO'en i ISO-mappen og genstart containeren. Filnavnet bliver spillets titel.
- **Gør et spil klar igen:** slet dets mappe under `/mnt/user/appdata/pixeline/` og genstart.

## Indhold

| Fil | Hvad |
|---|---|
| `server.py` | Webserver: spilliste, afspillerside og spilfiler (tåler forkerte store/små bogstaver i stierne) |
| `prepare.py` | Klargør en ISO: pakker ud, trækker startfilmen ud af .exe, retter Lingo-navne, små bogstaver |
| `player/` | Den rettede DirPlayer. `dirplayer-pixeline.patch` viser ændringerne i forhold til v0.8.1 |
| `unraid/` | Unraid-template og ikon |
| `.gitea/workflows/build.yml` | Automatisk build ved push (kræver en Gitea Actions-runner) |
