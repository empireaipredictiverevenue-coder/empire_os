import assert from 'node:assert/strict';
import test from 'node:test';

import postgres from 'postgres';

const DATABASE_URL = process.env.DATABASE_URL;

if (!DATABASE_URL) {
  test('competitor audience DB tests require DATABASE_URL', { skip: true }, () => {});
} else {
  const sql = postgres(DATABASE_URL, { max: 1 });

  const asRole = async (role, fn) =>
    sql.begin(async tx => {
      await tx.unsafe(`set local role ${role}`);
      return fn(tx);
    });

  test.after(async () => {
    await sql.end();
  });

  test('materializer has bounded competitor audience grants', async () => {
    const [row] = await sql`
      select
        has_table_privilege(
          'empire_intelligence_materializer',
          'public.business_entities',
          'SELECT'
        ) as entity_select,
        has_table_privilege(
          'empire_intelligence_materializer',
          'public.intelligence_signals',
          'SELECT'
        ) as signal_select,
        has_table_privilege(
          'empire_intelligence_materializer',
          'public.intelligence_signals',
          'INSERT'
        ) as signal_insert,
        has_table_privilege(
          'empire_intelligence_materializer',
          'public.intelligence_signals',
          'UPDATE'
        ) as signal_update,
        has_table_privilege(
          'empire_intelligence_materializer',
          'public.intelligence_signals',
          'DELETE'
        ) as signal_delete
    `;

    assert.equal(row.entity_select, true);
    assert.equal(row.signal_select, true);
    assert.equal(row.signal_insert, true);
    assert.equal(row.signal_update, false);
    assert.equal(row.signal_delete, false);
  });

  test('canonical competitor audience source exists', async () => {
    const rows = await sql`
      select id, source_key, source_type, enabled
      from public.intelligence_sources
      where source_key='empire.competitor_audience.public.v1'
    `;

    assert.equal(rows.length, 1);
    assert.equal(rows[0].source_type, 'other');
    assert.equal(rows[0].enabled, true);
  });

  test('materializer cannot update or delete canonical signals', async () => {
    await assert.rejects(
      asRole('empire_intelligence_materializer', tx =>
        tx`
          update public.intelligence_signals
          set strength=strength
          where false
        `
      )
    );

    await assert.rejects(
      asRole('empire_intelligence_materializer', tx =>
        tx`
          delete from public.intelligence_signals
          where false
        `
      )
    );
  });
}
