#!/bin/bash
# Fetch OSM highways for Kota Semarang in 3x3 tiles (Overpass), with retries.
S=-7.125; N=-6.918; W=110.257; E=110.519
i=0
for r in 0 1 2; do for c in 0 1 2; do
  s=$(python3 -c "print(round($S+($N-$S)*$r/3,4))"); n=$(python3 -c "print(round($S+($N-$S)*($r+1)/3,4))")
  w=$(python3 -c "print(round($W+($E-$W)*$c/3,4))"); e=$(python3 -c "print(round($W+($E-$W)*($c+1)/3,4))")
  f=roads_${r}_${c}.json
  [ -s $f ] && grep -q '"elements"' $f && continue
  q="[out:json][timeout:300][bbox:$s,$w,$n,$e];way[\"highway\"~\"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|track|path|footway|pedestrian|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|steps|road|cycleway|bridleway)$\"];out tags geom qt;"
  for t in 1 2 3 4 5 6 7 8 9 10; do
    for ep in https://overpass-api.de/api/interpreter https://overpass.private.coffee/api/interpreter https://overpass.kumi.systems/api/interpreter; do
      code=$(curl -s --max-time 400 -A "peta-semarang-data/1.0" -X POST --data-urlencode "data=$q" $ep -o $f -w "%{http_code}")
      echo "$f try $t $ep $code $(wc -c < $f 2>/dev/null)"
      [ "$code" = 200 ] && grep -q '"elements"' $f && break 2
      sleep 10
    done
  done
done; done
