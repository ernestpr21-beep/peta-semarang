#!/bin/bash
# OSM untuk model fitur (2026-10-8): tata guna lahan, sungai, garis pantai, bangunan (titik pusat, 3x3 petak)
B="-7.135,110.247,-6.908,110.529"
get() {
  local f="$1.json"; [ -s "$f.gz" ] && return
  for t in 1 2 3 4; do for ep in https://overpass.private.coffee/api/interpreter https://overpass-api.de/api/interpreter https://overpass.kumi.systems/api/interpreter; do
    code=$(curl -s --max-time 600 -A "peta-semarang-data/1.0" -X POST --data-urlencode "data=$2" $ep -o $f -w "%{http_code}")
    if [ "$code" = 200 ] && head -c 300 $f | grep -q elements && tail -c 50 $f | grep -q '}'; then gzip -f $f; echo "$1 ok $ep"; return; fi
    echo "$1 fail $code $ep"; sleep 8
  done; done
}
get lu "[out:json][timeout:600][bbox:$B];(way[landuse~\"^(industrial|commercial|retail|residential|farmland|paddy|orchard|forest|meadow|cemetery|military|port|plantation)$\"];relation[landuse~\"^(industrial|commercial|retail|residential|farmland|paddy|forest|orchard|plantation|port)$\"];);out tags geom qt;"
get wat "[out:json][timeout:600][bbox:$B];(way[waterway~\"^(river|canal)$\"];way[natural=coastline];);out tags geom qt;"
S=-7.135; N=-6.908; W=110.247; E=110.529
for r in 0 1 2; do for c in 0 1 2; do
  s=$(python3 -c "print(round($S+($N-$S)*$r/3,4))"); n=$(python3 -c "print(round($S+($N-$S)*($r+1)/3,4))")
  w=$(python3 -c "print(round($W+($E-$W)*$c/3,4))"); e=$(python3 -c "print(round($W+($E-$W)*($c+1)/3,4))")
  get bld_${r}_${c} "[out:json][timeout:600][bbox:$s,$w,$n,$e];way[building];out center qt;"
done; done
echo ALLDONE
# 2026-10-9: tambak/rawa/genangan untuk paparan rob
get wet "[out:json][timeout:600][bbox:$B];(way[landuse~\"^(aquaculture|salt_pond|basin|reservoir)$\"];way[natural=wetland];relation[natural=wetland];way[\"wetland\"];way[water~\"^(fishpond|pond|reservoir|basin)$\"];);out tags geom qt;"
