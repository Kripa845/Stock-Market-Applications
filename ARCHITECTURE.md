# Architecture

StockScope has three moving parts that share one PostgreSQL database:

1. **Collectors**: Scrapy spiders (`Backend/crawlers/`) plus a few direct HTTP clients in Django services. They run on a Celery beat schedule.
2. **Backend**: a Django + DRF project (`Backend/`) that stores, analyses and serves the data under `/api/`.
3. **Frontend**: a React + TypeScript SPA (`frontend/`) that calls the API with a JWT.

It is not deployed anywhere: it runs on one machine, natively on Windows or with `docker compose` (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).

## Data flow

```drawio locked
<mxfile>
  <diagram id="VgRqncqiKPkraNGRtt4z" name="Page-1">
    <mxGraphModel dx="2063" dy="1297" grid="1" gridSize="10" guides="1" tooltips="0" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <UserObject label="" mermaidData="{&#xa;  &quot;data&quot;: &quot;flowchart LR\n    subgraph Sources[\&quot;External sources (unofficial)\&quot;]\n        SS[ShareSansar]\n        SH[ShareHub]\n        NP[NEPSE via nepse-data-api]\n        NT[nepsetrading.com]\n        NEWS[News sites]\n    end\n\n    subgraph Workers[\&quot;Celery worker (queue: crawling)\&quot;]\n        BEAT[[Celery beat&lt;br/&gt;DatabaseScheduler]]\n        RUN[crawler_runs.tasks&lt;br/&gt;runner.run_spider]\n        SPIDER[scrapy crawl &amp;lt;spider&amp;gt;&lt;br/&gt;subprocess]\n        SVC[Direct-fetch services&lt;br/&gt;live_prices, nepse_indices,&lt;br/&gt;sharehub_floorsheet, nepsetrading]\n        DERIVE[Derive tasks&lt;br/&gt;analysis, market_intelligence,&lt;br/&gt;categorize news]\n    end\n\n    DB[(PostgreSQL)]\n    REDIS[(Redis&lt;br/&gt;broker + circuit breaker)]\n    API[Django / DRF&lt;br/&gt;/api/...]\n    UI[React SPA]\n\n    BEAT --&gt; REDIS --&gt; RUN --&gt; SPIDER\n    BEAT --&gt; SVC\n    SS &amp; NEWS --&gt; SPIDER\n    SPIDER --&gt;|pipelines upsert| DB\n    SH &amp; NP &amp; NT &amp; SS --&gt; SVC --&gt;|update_or_create| DB\n    DB --&gt; DERIVE --&gt; DB\n    DB --&gt; API --&gt;|JSON, JWT| UI&quot;,&#xa;  &quot;config&quot;: null&#xa;}" id="34">
          <mxCell connectable="0" parent="1" style="group;transparentBounds=1;editIcon=1;lockedGroup=0;groupPadding=10;" vertex="1">
            <mxGeometry as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="External sources (unofficial)" mermaidId="n:Sources" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;verticalAlign=top;fillColor=light-dark(#ffffde,#1f2020);strokeColor=light-dark(#aaaa33,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="External sources (unofficial)" id="2">
          <mxCell parent="34" style="html=1;whiteSpace=wrap;strokeWidth=1;verticalAlign=top;fillColor=light-dark(#ffffde,#1f2020);strokeColor=light-dark(#aaaa33,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="540" width="312" x="489" y="497" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="ShareSansar" mermaidId="n:SS" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="ShareSansar" id="3">
          <mxCell parent="2" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="146" x="83" y="461" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="ShareHub" mermaidId="n:SH" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="ShareHub" id="4">
          <mxCell parent="2" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="128" x="92" y="357" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="NEPSE via nepse-data-api" mermaidId="n:NP" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="NEPSE via nepse-data-api" id="5">
          <mxCell parent="2" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="242" x="35" y="253" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="nepsetrading.com" mermaidId="n:NT" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="nepsetrading.com" id="6">
          <mxCell parent="2" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="188" x="62" y="149" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="News sites" mermaidId="n:NEWS" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="News sites" id="7">
          <mxCell parent="2" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="135" x="89" y="45" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Celery worker (queue: crawling)" mermaidId="n:Workers" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;verticalAlign=top;fillColor=light-dark(#ffffde,#1f2020);strokeColor=light-dark(#aaaa33,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Celery worker (queue: crawling)" id="8">
          <mxCell parent="34" style="html=1;whiteSpace=wrap;strokeWidth=1;verticalAlign=top;fillColor=light-dark(#ffffde,#1f2020);strokeColor=light-dark(#aaaa33,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="361" width="1774" x="10" y="116" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Celery beat&#xa;DatabaseScheduler" mermaidId="n:BEAT" mermaidBaseStyle="html=1;strokeWidth=1;shape=process;whiteSpace=wrap;size=0.04;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Celery beat&#xa;DatabaseScheduler" id="9">
          <mxCell parent="8" style="html=1;strokeWidth=1;shape=process;whiteSpace=wrap;size=0.04;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="53" width="168" x="35" y="117" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="crawler_runs.tasks&#xa;runner.run_spider" mermaidId="n:RUN" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="crawler_runs.tasks&#xa;runner.run_spider" id="10">
          <mxCell parent="8" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="73" width="194" x="538" y="45" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="scrapy crawl &amp;lt;spider&amp;gt;&#xa;subprocess" mermaidId="n:SPIDER" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="scrapy crawl &amp;lt;spider&amp;gt;&#xa;subprocess" id="11">
          <mxCell parent="8" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="73" width="215" x="879" y="120" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Direct-fetch services&#xa;live_prices, nepse_indices,&#xa;sharehub_floorsheet, nepsetrading" mermaidId="n:SVC" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Direct-fetch services&#xa;live_prices, nepse_indices,&#xa;sharehub_floorsheet, nepsetrading" id="12">
          <mxCell parent="8" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="93" width="310" x="831" y="243" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Derive tasks&#xa;analysis, market_intelligence,&#xa;categorize news" mermaidId="n:DERIVE" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Derive tasks&#xa;analysis, market_intelligence,&#xa;categorize news" id="13">
          <mxCell parent="8" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="93" width="276" x="1463" y="136" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:RUN-&gt;SPIDER#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0.09;entryY=0;" mermaidBaseValue="" id="32">
          <mxCell edge="1" parent="8" source="10" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0.09;entryY=0;" target="11">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="781" y="82" />
                <mxPoint x="806" y="82" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:BEAT-&gt;SVC#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.64;entryX=0.3;entryY=0;" mermaidBaseValue="" id="33">
          <mxCell edge="1" parent="8" source="9" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.64;entryX=0.3;entryY=0;" target="12">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="228" y="153" />
                <mxPoint x="346" y="153" />
                <mxPoint x="464" y="153" />
                <mxPoint x="489" y="153" />
                <mxPoint x="635" y="153" />
                <mxPoint x="781" y="153" />
                <mxPoint x="806" y="153" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="PostgreSQL" mermaidId="n:DB" mermaidBaseStyle="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="PostgreSQL" id="14">
          <mxCell parent="34" style="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="67" width="94" x="1329" y="524" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Redis&#xa;broker + circuit breaker" mermaidId="n:REDIS" mermaidBaseStyle="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Redis&#xa;broker + circuit breaker" id="15">
          <mxCell parent="34" style="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="81" width="186" x="263" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Django / DRF&#xa;/api/..." mermaidId="n:API" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Django / DRF&#xa;/api/..." id="16">
          <mxCell parent="34" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="73" width="155" x="1534" y="522" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="React SPA" mermaidId="n:UI" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="React SPA" id="17">
          <mxCell parent="34" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="129" x="1902" y="532" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:BEAT-&gt;REDIS#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.78;exitY=0;entryX=0.32;entryY=1;" mermaidBaseValue="" id="18">
          <mxCell edge="1" parent="34" source="9" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.78;exitY=0;entryX=0.32;entryY=1;" target="15">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="238" y="198" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:REDIS-&gt;RUN#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.68;exitY=1;entryX=0;entryY=0.51;" mermaidBaseValue="" id="19">
          <mxCell edge="1" parent="34" source="15" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.68;exitY=1;entryX=0;entryY=0.51;" target="10">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="474" y="198" />
                <mxPoint x="499" y="198" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:SS-&gt;SPIDER#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.11;entryX=0.32;entryY=1;" mermaidBaseValue="" id="20">
          <mxCell edge="1" parent="34" source="3" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.11;entryX=0.32;entryY=1;" target="11">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="791" y="943" />
                <mxPoint x="816" y="446" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:NEWS-&gt;SPIDER#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0;entryY=0.63;" mermaidBaseValue="" id="21">
          <mxCell edge="1" parent="34" source="7" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0;entryY=0.63;" target="11">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="791" y="569" />
                <mxPoint x="816" y="289" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="pipelines upsert" mermaidId="e:SPIDER-&gt;DB#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0.33;entryY=0;" mermaidBaseValue="pipelines upsert" id="22">
          <mxCell edge="1" parent="34" source="11" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0.33;entryY=0;" target="14">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1240" y="273" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:SH-&gt;SVC#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0;entryY=0.69;" mermaidBaseValue="" id="23">
          <mxCell edge="1" parent="34" source="4" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0;entryY=0.69;" target="12">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="791" y="881" />
                <mxPoint x="816" y="426" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:NP-&gt;SVC#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0;entryY=0.51;" mermaidBaseValue="" id="24">
          <mxCell edge="1" parent="34" source="5" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0;entryY=0.51;" target="12">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="791" y="777" />
                <mxPoint x="816" y="406" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:NT-&gt;SVC#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0.09;entryY=0;" mermaidBaseValue="" id="25">
          <mxCell edge="1" parent="34" source="6" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.5;entryX=0.09;entryY=0;" target="12">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="791" y="673" />
                <mxPoint x="816" y="340" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:SS-&gt;SVC#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.61;entryX=0.05;entryY=1;" mermaidBaseValue="" id="26">
          <mxCell edge="1" parent="34" source="3" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.61;entryX=0.05;entryY=1;" target="12">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="791" y="996" />
                <mxPoint x="816" y="466" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="update_or_create" mermaidId="e:SVC-&gt;DB#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0.18;entryY=0;" mermaidBaseValue="update_or_create" id="27">
          <mxCell edge="1" parent="34" source="12" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0.18;entryY=0;" target="14">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1240" y="406" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:DB-&gt;DERIVE#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5638297872340425;exitY=0;entryX=0.5217391304347826;entryY=1;curved=1;exitX=0.56;exitY=0;entryX=0.52;entryY=1;" mermaidBaseValue="" id="28">
          <mxCell edge="1" parent="34" source="14" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.56;exitY=0;entryX=0.52;entryY=1;" target="13">
            <mxGeometry relative="1" as="geometry">
              <mxPoint as="offset" />
              <Array as="points">
                <mxPoint x="1506" y="435" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:DERIVE-&gt;DB#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.4782608695652174;exitY=1;entryX=0.43617021276595747;entryY=0;curved=1;exitX=0.48;exitY=1;entryX=0.44;entryY=0;" mermaidBaseValue="" id="29">
          <mxCell edge="1" parent="34" source="13" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.48;exitY=1;entryX=0.44;entryY=0;" target="14">
            <mxGeometry relative="1" as="geometry">
              <mxPoint as="offset" />
              <Array as="points">
                <mxPoint x="1482" y="435" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:DB-&gt;API#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0;entryY=0.51;" mermaidBaseValue="" id="30">
          <mxCell edge="1" parent="34" source="14" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0;entryY=0.51;" target="16">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1448" y="559" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="JSON, JWT" mermaidId="e:API-&gt;UI#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0;entryY=0.5;" mermaidBaseValue="JSON, JWT" id="31">
          <mxCell edge="1" parent="34" source="16" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.51;entryX=0;entryY=0.5;" target="17">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

## Directory map

```
Backend/
├── config/            settings.py (beat schedule, task routes, thresholds), urls.py, celery.py, settings_test.py
├── apps/<app>/        one Django app per area (layout below)
├── crawlers/          separate Scrapy project
│   ├── runner.py      launches spiders as subprocesses; spider lists (NEWS_SPIDERS, ...)
│   └── crawlers/      settings.py, items.py, pipelines.py (+ market_wide/dividend/ipo pipelines), spiders/
├── data/              seed files: brokers.csv, stock_sectors.csv, company_logos.json, backups/
└── scripts/           one-off scripts (crawl_company_logos.py)
frontend/src/
├── api/               one module per backend area, on top of api/client.ts (axios + JWT refresh)
├── hooks/             TanStack Query wrappers around api/
├── pages/             one file per route (routes in App.tsx)
├── components/        grouped by area: market, brokers, charts, calendar, admin, layout, ...
├── config/            routePermissions.ts (frontend copy of the permission rules)
└── contexts/          AuthContext (user, permissions, tokens)
docs/                  DATABASE, API, DATA_SOURCES, SECURITY, TESTING, DEPLOYMENT, GLOSSARY, status, project-log, features/
```

Every backend app has the same layout:

```
apps/<app>/
├── models.py              tables
├── api/                   urls.py, views.py, serializers.py (thin views)
├── services/              business logic, one file per feature
├── tasks.py               Celery tasks (scheduled in config/settings.py → CELERY_BEAT_SCHEDULE)
├── management/commands/   python manage.py <command>
├── tests/test_<feature>.py
└── README.md              what the app owns
```

## Core components

| App | Owns | Main models |
|---|---|---|
| `users` | Users, roles, permission keys, per-user company access | `User`, `CustomRole`, `RolePermissionConfig`, `UserCompanyAccess`, `Watchlist` |
| `companies` | Company list, tracked companies, stock quote and MASTER score data | `Company`, `TrackedCompany`, `Shareholding`, `MasterScore` |
| `market_data` | Daily prices, live prices, movers, heatmap, watchlists, trading calendar | `DailyPrice`, `TradingHoliday`, `LiveFeedStatus` |
| `floorsheet` | Every trade (buyer / seller broker), broker directory, intraday candles | `FloorsheetTransaction`, `Broker`, `IntradayCandle` |
| `reports` | Dividends, EPS, quarterly reports, IPO issues, CSV / XLSX / PDF exports | `DividendAnnouncement`, `CompanyEarnings`, `QuarterlyReport`, `YearlyDPPS`, `IpoIssue` |
| `market_indices` | NEPSE + 13 sub-indices, whole-market daily rows, index replication | `MarketIndex`, `IndexDaily`, `IndexIntradayPoint`, `MarketStockDaily`, `CompanyDaily` |
| `market_intelligence` | ~110 technical indicators (computed on request), breadth, sector rotation, support / resistance | `*Snapshot`, `SupportResistanceSet` |
| `analysis` | Broker accumulation / position, floorsheet grid, daily pressure, volume anomalies, news vs price | `DailyAnalysis`, `VolumeAnomaly`, `NewsPriceCorrelation` |
| `news` | Crawled articles, company tagging, sentiment | `NewsArticle`, `ArticleCompanyTag`, `CategorizationCorrection` |
| `announcements` | ShareHub market and tracked-company announcements and events | `Announcement` |
| `crawler_runs` | Starting spiders and recording each run | `CrawlRun` |
| `dashboard` | Role dashboards and export endpoints | none |
| `market_calendar` | BS / AD month calendar, weekday / day-by-day / month-by-month summaries | none (derived) |
| `comparison` | Side-by-side profile of 2–5 tracked companies, data-coverage report (`/api/compare/`, [docs/features/stock-comparison.md](docs/features/stock-comparison.md)) | none (derived) |
| `financial_reports` | Nepalipaisa filing document metadata and sync command | `FinancialReport` |

**Dependency direction:** `users`, `companies` → `market_data`, `floorsheet`, `reports`, `market_indices` → `analysis`, `market_intelligence`, `dashboard`, `market_calendar` → `comparison`. Lower layers never import upper ones.

Full table list: [docs/DATABASE.md](docs/DATABASE.md). Endpoints: [docs/API.md](docs/API.md).

## Key scenarios

### Evening price crawl (trading days, 18:00 NPT)

1. Beat fires `crawler_runs.tasks.crawl_daily_prices`, which creates a `CrawlRun` and starts a Celery `chain`: `run_crawl` → `derive_price_fields_task` → `rebuild_all_analysis` → `compute_support_resistance_task` (`apps/crawler_runs/tasks.py`).
2. `run_crawl` calls `crawlers/runner.py::run_spider("trading_data")`, which runs `python -m scrapy crawl trading_data` as a subprocess with a timeout.
3. The spider reads ShareSansar; `TradingDataPipeline` (`crawlers/crawlers/pipelines.py`) upserts `DailyPrice` rows with `source="crawled"`.
4. Later beat jobs build on it: whole-market rows (18:10), floorsheet (18:15), analysis (18:45), market intelligence (19:00).

### Live session (trading days, 11:00–15:15 NPT)

* Every 2 min `market_data.tasks.update_live_prices` calls NEPSE through `nepse-data-api` (`services/live_prices.py`) and writes `Company.ltp`, `session_volume`, `session_turnover`, plus a `LiveFeedStatus` row.
* Every 5 min `market_indices.tasks.snapshot_live_index` stores `IndexIntradayPoint` ticks. After 3 failures in a row a circuit breaker held in Redis stops calls for 30 min.
* Every 5 min `floorsheet.tasks.build_intraday_candles_live` pulls ShareHub trades with times and rebuilds `IntradayCandle`.

### News

Hourly `crawl_all_news` runs the five news spiders in `NEWS_SPIDERS`; `NewsPipeline` hands each item to `news/services/ingest.py::ingest_article`, which upserts per source by external id / normalised URL and links the same story across sources (`apps/news/README.md`). Every 10 min `news.tasks.categorize_unprocessed_news_task` tags companies (embeddings + keyword matching, `news/services/categorization.py`). Spec: [docs/features/news-categorization.md](docs/features/news-categorization.md).

### A page request

1. The SPA route is guarded by `PermissionRoute` with a rule from `config/routePermissions.ts`.
2. The `api/` module sends `Authorization: Bearer <access>`; on 401 `api/client.ts` refreshes once (shared promise) and retries.
3. The DRF view checks `HasAppPermission` (`permission_key` or any-of `permission_keys`) and narrows companies with `apps/users/company_access.py`. Legacy broad keys remain valid alongside page-level keys; see [docs/ROLE_PERMISSIONS.md](docs/ROLE_PERMISSIONS.md).
4. The view calls a service; prices come only from `source="crawled"` rows (`market_data/services/price_source.py::with_crawled_price`).

## Frontend route → API → backend

Routes are in `frontend/src/App.tsx`, rules in `config/routePermissions.ts`, pages in `frontend/src/pages/`.

| Route → page | API | Backend |
|---|---|---|
| `/dashboard` → `Dashboard.tsx` | `/api/dashboard/…` | `dashboard/api/views.py` |
| `/market` → `Market.tsx` | `/api/market/summary`, `overview`, `movers`, `heatmap` | `market_data/api/market_views.py` |
| `/market/gainers`, `/market/losers` → `TopMoversPage.tsx` | `/api/market/movers/`, `top-gainers/` | `market_data/services/movers.py`, `top_movers.py` |
| `/market/turnover`, `volume`, `transactions` → `TopActivityPage.tsx` | `/api/market/top-activity/`, `top-*` | `market_data/api/market_views.py` |
| `/market/indices` → `IndicesPage.tsx` | `/api/market-indices/…` | `market_indices/api/views.py` |
| `/market/day-by-day` → `DayByDayPage.tsx` | `/api/market-calendar/months/` | `market_calendar/services/month_summary.py` |
| `/market/month-by-month` → `MonthByMonthPage.tsx` | `/api/market-calendar/monthly/` | `market_calendar/services/monthly_returns.py` |
| `/market/dividends` → `DividendsPage.tsx` | `/api/market/dividends/` | `reports/services/dividends.py` |
| `/market/quarterly-report/:sector` → `QuarterlyReportPage.tsx` | `/api/market/quarterly-report/` | `reports/services/quarterly_reports.py`, `quarterly_metrics.py` |
| `/financial-reports` → `FinancialReports.tsx` | `/api/financial-reports/`, `/api/financial-reports/filters/` | `financial_reports/views.py`, `FinancialReport`; sync via `sync_financial_reports` |
| `/companies` → `admin/CompaniesPage.tsx` | `/api/companies/` | `companies/api/views.py` |
| `/stocks/:symbol` → `stock-detail/StockDetailsPage.tsx` | `/api/companies/` (tracked list and quote), `/api/companies/<id>/{performance,valuation,master-score}/`, `/api/stocks/<symbol>/intraday/` | `companies/api/`, `market_data/services/{stock_performance,market_beta}.py`, `analysis/services/master_score.py`, `reports/services/quarterly_reports.py`, `floorsheet/` |
| `/companies/:symbol` → legacy `StockDetail.tsx` | `/api/companies/<id>/…`, `/api/stocks/<symbol>/intraday/`, `/api/analysis/broker-*` | `companies/`, `floorsheet/`, `analysis/services/broker_accumulation.py` |
| `/floorsheet` → `FloorsheetPage.tsx` | `/api/floorsheet/`, `summary/` | `floorsheet/api/views.py` |
| `/floorsheet/summary` → `FloorsheetSummaryPage.tsx` | `/api/analysis/floorsheet-grid/` | `analysis/services/floorsheet_grid.py` |
| `/technical-charts` → `TechnicalCharts.tsx` | `/api/market-intelligence/…`, `/api/market-indices/…` (intraday: `/api/companies/<id>/intraday/`, `/api/market-indices/intraday/`) | `market_intelligence/indicators/`, `services/technicals.py`, `floorsheet/services/intraday.py` |
| `/company-analysis` → `CompanyAnalysisDashboard.tsx` | `/api/analysis/…`, `/api/market-intelligence/…`, `/api/companies/<id>/intraday/` | `analysis/`, `market_intelligence/`, `floorsheet/services/intraday.py` |
| `/broker-analysis[/:brokerId]` → `BrokerAnalysisPage.tsx` | `/api/analysis/brokers/…` | `analysis/services/brokers.py` |
| `/top-brokers[/:broker]` → `TopBrokerPage.tsx`, `TopBrokerStocksPage.tsx` | `/api/analysis/brokers/top/`, `brokers/<id>/` | `analysis/services/brokers.py` |
| `/brokers` → `BrokerListPage.tsx` | `/api/analysis/brokers/list/` | `analysis/api/views.py` |
| `/broker-acc-dist` → `AccDistPage.tsx` | `/api/analysis/acc-dist/` | `analysis/services/broker_accumulation.py` |
| `/broker-position` → `BrokerPositionPage.tsx` | `/api/analysis/broker-position/`, `broker-activity/` | `analysis/services/broker_position.py` |
| `/watchlist` → `MyWatchlistPage.tsx` | `/api/market/watchlists/…` | `market_data/api/watchlists.py`, `services/watchlist.py` |
| `/live-trading` → `WatchlistPage.tsx`, `/watchlist-comparison` → `WatchlistComparison.tsx` | `/api/market/…`, `/api/floorsheet/` | `market_data/`, `floorsheet/` |
| `/compare` → `StockComparisonPage.tsx` | `/api/compare/`, `/api/compare/companies/` | `comparison/services/compare.py` |
| `/news[/:id]` → `News.tsx`, `NewsDetail.tsx` | `/api/news/…` | `news/api/views.py` |
| `/announcements` → `announcements/Announcementspage.tsx` | `/api/announcements/`, `/api/announcements/filters/` | `announcements/views.py`, `services.py` |
| `/crawl` → `CrawlerStatus.tsx` | `/api/crawler-runs/…` | `crawler_runs/api/views.py`, `tasks.py` |
| `/reports` → `ExportPage.tsx` | `/api/reports/export/…` | `reports/exports/` |
| `/users`, `/roles-permissions` → `admin/UserManagementPage.tsx`, `admin/RolesPermissionPage.tsx` | `/api/users/admin/…` | `users/api/views.py` |

`/admin/*` and `/analyst/*` paths redirect to the routes above; `/brokers-distribution` redirects to `/broker-acc-dist`.

## Design decisions

What the code and its comments show; the "why" is quoted from comments where one exists.

| Decision | Where | Reason |
|---|---|---|
| **Tracked companies only** (about 20), except index, dividend, IPO and market-wide broker pages | `companies/services/selection.py::tracked_active_companies` | A focused research set, not a market terminal. TODO: confirm reason. |
| **Real data only**: `DailyPrice.source` separates `crawled` from synthetic `unverified` / `seeded` rows; missing data is shown as missing | `market_data/services/price_source.py` | Synthetic seed rows exist from early development and must never reach charts or analysis. |
| **Each spider runs in its own subprocess** | `crawlers/runner.py` | A run can be killed on timeout (whole process group on Linux). TODO: confirm; probably also because Scrapy's Twisted reactor can't restart inside a long-lived worker. |
| **Pipelines upsert** on natural keys | `crawlers/crawlers/pipelines.py` | Re-running any crawl or backfill is safe. |
| **Worker `--pool=solo`, one queue `crawling`** | `docker-compose.yml`, `CELERY_TASK_ROUTES` | "Required on Windows and works on Linux too" (compose comment). With concurrency 1, tasks run one at a time. TODO: confirm that's also intended to keep sources from being hit in parallel. |
| **Live-feed state in the DB, circuit breaker in Redis** | `LiveFeedStatus`, `market_indices/tasks.py` | Worker and web server don't share Django's per-process cache. |
| **Moved models keep `market_data_*` table names** | `floorsheet`, `reports` models (`db_table`) | Splitting the apps needed no data copy. |
| **One definition of session change** | `market_data/services/movers.py` | Gainers / losers / calendar / weekday pages all agree. |
| **Indicators computed on request, not stored** | `market_intelligence/indicators/registry.py` | Avoids a large table of derived values; they return `None` during warm-up, never 0. |
| **Dates stored in AD; BS conversion only on the backend** via `nepali_datetime` | `market_calendar/services/` | One conversion path; the frontend has no BS library. |
| **Time zone** `Asia/Kathmandu` for Django and Celery, `USE_TZ=True` (DB stores UTC) | `config/settings.py` | Beat times and "today" must match the NEPSE session. |
| **Prices stored as `Decimal`; floats only in computed outputs** (statistics, JSON) | models vs `services/*` | TODO: confirm whether API responses should stay float. |
| **Unofficial sources** | spiders, services | Acceptable for a personal app; check their terms before any public use. |
