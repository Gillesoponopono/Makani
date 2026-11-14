<script lang="ts">
  // "Guide & sources" (menu → #/guide): how to read the forecast, where the data comes
  // from, and the usual warning. Kept off the forecast screen so it stays uncluttered.
  import { dateLong, timeAgo } from '../lib/format'
  import type { Meta, SpotDoc } from '../lib/types'

  let { meta, docs, backHref, backName }: { meta: Meta; docs: SpotDoc[]; backHref: string; backName: string } = $props()

  const adjusted = $derived(docs.filter((d) => d.adjusted))
</script>

<article class="guide">
  <a class="back" href={backHref}>← {backName}</a>
  <h1 class="display">Guide &amp; sources</h1>
  <p class="lede">
    How to read Makani's forecast, where every number comes from, and what it can't tell you. Model run through
    {dateLong(meta.wrf.end.slice(0, 10))}, updated {timeAgo(meta.generatedAt)}.
  </p>

  <section class="card">
    <h2 class="display">Reading the chart</h2>
    <dl>
      <dt>Wind</dt>
      <dd>
        The coloured line is the model's wind at 10 m, from a 2 km cell just offshore of the spot, coloured by
        strength. The amber band is the best session: the longest daylight stretch that suits at least one sport.
      </dd>
      <dt>Gusts</dt>
      <dd>The grey line is an estimate: wind × {meta.ratings.gustFactor}. The model doesn't forecast gusts.</dd>
      <dt>Adjusted</dt>
      <dd>
        The dashed line is the model corrected with 14 months of forecasts compared with what nearby weather stations
        measured: the model tends to announce too much wind, more so when it announces a lot. It is fitted separately
        for trade winds and other directions, by day and by night. The stations aren't on the beach, which may get more
        wind, so read it as "what the station would show".
        {#if adjusted.length}
          <ul class="figures">
            {#each adjusted as d (d.id)}
              {@const a = d.adjusted!}
              <li>
                <strong>{d.displayName}</strong>:
                {#if a.transferredFrom}
                  no station nearby, so it uses the correction fitted for
                  {docs.find((x) => x.id === a.transferredFrom)?.displayName ?? a.transferredFrom}. An estimate, not checked.
                {:else}
                  typical miss in kiting hours {a.maeRaw?.toFixed(1)} → {a.maeAdj?.toFixed(1)} kn, against the {a.reference}.
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </dd>
      <dt>Direction</dt>
      <dd>
        Arrows under the chart point where the wind blows: <span class="s-good">good</span>,
        <span class="s-ok">OK</span>, <span class="s-poor">poor</span> or <span class="s-danger">offshore</span> for
        this spot. In the hourly table: ✓ good, ~ OK, · poor, ⚠ offshore.
      </dd>
      <dt>Sky</dt>
      <dd>
        Sun, partly cloudy, cloudy or showers, from the sunshine the model lets through to the ground and its rain. A
        single model run gives no probability, so there is no "chance of rain"; the rain rate is shown when it rains.
      </dd>
      <dt>Waves</dt>
      <dd>
        Height just off the beach and peak period (PacIOOS SWAN, 500 m). The type (swell, wind chop, both, flat)
        comes from the offshore split between swell and wind waves (WaveWatch III). Wind chop blowing out to sea isn't
        counted. Kahului Harbor is sheltered: flat water, wind chop only.
      </dd>
      <dt>Tide</dt>
      <dd>
        NOAA predictions above mean lower low water, for Kahului (north shore) and Makena (Kīhei side, where NOAA gives
        only the highs and lows, so the curve in between is estimated).
      </dd>
      <dt>Water</dt>
      <dd>Sea surface temperature from the PacIOOS ROMS ocean model, just offshore.</dd>
      <dt>Units</dt>
      <dd>Wind in knots, mph or km/h. Heights follow the temperature choice: metres with °C, feet with °F.</dd>
      <dt>Map</dt>
      <dd>Red dots are the anemometers (Kahului Harbor and Airport), the yellow dot the Pauwela wave buoy.</dd>
    </dl>
  </section>

  <section class="card">
    <h2 class="display">Data sources</h2>
    <ul class="sources">
      <li>
        Wind, air, sky: <a href="https://www.pacioos.hawaii.edu/weather/model-wind-maui/">PacIOOS WRF Maui-Oʻahu</a>
        (University of Hawaiʻi, Yi-Leng Chen), funded by NOAA/IOOS.
      </li>
      <li>
        Waves: <a href="https://www.pacioos.hawaii.edu/waves/model-maui/">PacIOOS SWAN Maui</a> and
        <a href="https://www.pacioos.hawaii.edu/waves/model-hawaii/">WaveWatch III Hawaiʻi</a>.
      </li>
      <li>Sea temperature: <a href="https://www.pacioos.hawaii.edu/currents/model-hawaii/">PacIOOS ROMS Hawaiʻi</a>.</li>
      <li>
        Tides: <a href="https://tidesandcurrents.noaa.gov/">NOAA CO-OPS</a> predictions for Kahului (1615680) and
        Makena (1615202).
      </li>
      <li>
        Measured wind for the adjusted forecast: NOAA CO-OPS Kahului Harbor (1615680) and the Kahului Airport (PHOG)
        station, via the NWS and the Iowa Environmental Mesonet archive.
      </li>
      <li>
        Map: spots placed with the US Census coastline (Hawaiʻi Statewide GIS Program). The island picture is
        illustrative.
      </li>
    </ul>
  </section>

  <section class="card warning">
    <h2 class="display">Be careful</h2>
    <p>
      Forecasts can be wrong. Makani doesn't replace checking conditions on the beach, local knowledge or official NWS
      warnings. Kite at your own risk.
    </p>
  </section>
</article>

<style>
  .guide {
    max-width: 780px;
    margin: 0 auto;
  }
  .back {
    display: inline-block;
    margin: 4px 0 14px;
    color: var(--muted);
    text-decoration: none;
    font-weight: 600;
  }
  .back:hover {
    color: var(--text);
  }
  h1 {
    margin: 0 0 8px;
    font-size: clamp(2rem, 5vw, 2.8rem);
    font-weight: 700;
    line-height: 1.05;
  }
  .lede {
    margin: 0 0 22px;
    color: var(--muted);
  }
  section {
    margin-bottom: 14px;
    padding: 18px 22px;
  }
  h2 {
    margin: 0 0 12px;
    font-size: 1.25rem;
    font-weight: 600;
  }
  dl {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 10px 18px;
    margin: 0;
  }
  dt {
    font-weight: 700;
    color: var(--text);
  }
  dd {
    margin: 0;
    color: var(--muted);
  }
  .figures {
    margin: 8px 0;
    padding-left: 18px;
  }
  .figures strong {
    color: var(--text);
  }
  .sources {
    margin: 0;
    padding-left: 18px;
    color: var(--muted);
  }
  .sources li + li {
    margin-top: 6px;
  }
  .guide a:not(.back) {
    color: var(--text);
  }
  .warning p {
    margin: 0;
    color: var(--muted);
  }
  @media (max-width: 600px) {
    section {
      padding: 14px 14px;
    }
    dl {
      grid-template-columns: 1fr;
      gap: 2px;
    }
    dd {
      margin-bottom: 10px;
    }
  }
</style>
