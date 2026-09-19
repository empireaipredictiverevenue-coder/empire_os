import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');

const {default:EmbeddedPostgres}=await import(pathToFileURL(
  join(deps,'node_modules/embedded-postgres/dist/index.js')
));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-score-v2-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),
  user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55464,
  persistent:true,
  createPostgresUser:false,
  onLog:()=>{},
  onError:()=>{},
});

let admin;
let passed=0;

async function test(name,fn){
  await fn();
  passed++;
  console.log('PASS '+name);
}

try{
  await pg.initialise();
  await pg.start();
  admin=pg.getPgClient();
  await admin.connect();

  await admin.query(
    "create table public.prospect_qualifications("+
    "id uuid primary key default gen_random_uuid(),"+
    "prospect_id uuid not null,"+
    "score numeric not null default 0,"+
    "tier text not null default 'dead',"+
    "data_completeness_score numeric not null default 0,"+
    "business_presence_score numeric not null default 0,"+
    "market_fit_score numeric not null default 0,"+
    "engagement_potential_score numeric not null default 0,"+
    "enrichment_quality_score numeric not null default 0,"+
    "scoring_engine text not null default 'empire_os.lead_scoring',"+
    "scoring_version text not null default 'v1',"+
    "result_payload jsonb not null default '{}'::jsonb,"+
    "status text not null default 'scored',"+
    "scored_at timestamptz not null default now(),"+
    "unique(prospect_id,scoring_engine,scoring_version)"+
    ")"
  );

  const prospect=
    '00000000-0000-0000-0000-000000000001';

  await admin.query(
    "insert into public.prospect_qualifications("+
    "prospect_id,score,tier,data_completeness_score,"+
    "business_presence_score,market_fit_score,"+
    "engagement_potential_score,enrichment_quality_score"+
    ") values($1,37,'cold',30,25,100,0,0)",
    [prospect],
  );

  const migration=await readFile(
    join(
      root,
      'supabase/migrations/',
      '20260919113646_lead_scoring_v2_evidence.sql',
    ),
    'utf8',
  );
  await admin.query(migration);

  await test('existing v1 row survives unchanged',async()=>{
    const row=(await admin.query(
      "select score,tier,scoring_version,"+
      "engagement_potential_score,enrichment_quality_score "+
      "from public.prospect_qualifications "+
      "where prospect_id=$1 and scoring_version='v1'",
      [prospect],
    )).rows[0];

    assert.equal(Number(row.score),37);
    assert.equal(row.tier,'cold');
    assert.equal(row.scoring_version,'v1');
    assert.equal(Number(row.engagement_potential_score),0);
    assert.equal(Number(row.enrichment_quality_score),0);
  });

  await test('v2 can preserve unknown dimensions as null',async()=>{
    const second=
      '00000000-0000-0000-0000-000000000002';
    await admin.query(
      "insert into public.prospect_qualifications("+
      "prospect_id,score,tier,data_completeness_score,"+
      "business_presence_score,market_fit_score,"+
      "engagement_potential_score,enrichment_quality_score,"+
      "scoring_version,evidence_confidence,"+
      "observed_dimensions,unknown_dimensions"+
      ") values($1,100,'insufficient_evidence',15,"+
      "null,100,null,null,'v2',0.15,$2::jsonb,$3::jsonb)",
      [
        second,
        JSON.stringify(['market_fit']),
        JSON.stringify([
          'business_presence',
          'engagement_potential',
          'enrichment_quality',
        ]),
      ],
    );

    const row=(await admin.query(
      "select * from public.prospect_qualifications "+
      "where prospect_id=$1 and scoring_version='v2'",
      [second],
    )).rows[0];

    assert.equal(row.business_presence_score,null);
    assert.equal(row.engagement_potential_score,null);
    assert.equal(row.enrichment_quality_score,null);
    assert.equal(Number(row.evidence_confidence),0.15);
    assert.deepEqual(row.observed_dimensions,['market_fit']);
  });

  await test('v1 and v2 coexist for same prospect',async()=>{
    await admin.query(
      "insert into public.prospect_qualifications("+
      "prospect_id,score,tier,data_completeness_score,"+
      "business_presence_score,market_fit_score,"+
      "engagement_potential_score,enrichment_quality_score,"+
      "scoring_version,evidence_confidence"+
      ") values($1,100,'insufficient_evidence',15,"+
      "null,100,null,null,'v2',0.15)",
      [prospect],
    );

    const rows=(await admin.query(
      "select scoring_version from public.prospect_qualifications "+
      "where prospect_id=$1 order by scoring_version",
      [prospect],
    )).rows.map(r=>r.scoring_version);

    assert.deepEqual(rows,['v1','v2']);
  });

  await test('confidence outside 0..1 is rejected',async()=>{
    await assert.rejects(
      admin.query(
        "insert into public.prospect_qualifications("+
        "prospect_id,scoring_version,evidence_confidence"+
        ") values("+
        "'00000000-0000-0000-0000-000000000003','v2',1.2)",
      ),
      /evidence_confidence_check/,
    );
  });

  await test('observed dimensions must be array',async()=>{
    await assert.rejects(
      admin.query(
        "insert into public.prospect_qualifications("+
        "prospect_id,scoring_version,observed_dimensions"+
        ") values("+
        "'00000000-0000-0000-0000-000000000004',"+
        "'v2','{}'::jsonb)",
      ),
      /observed_dimensions_array_check/,
    );
  });

  console.log(
    passed+
    ' Lead Scoring v2 schema tests passed; '+
    'no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
