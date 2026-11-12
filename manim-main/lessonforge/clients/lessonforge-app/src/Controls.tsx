// Every switch the pipeline has, as controls for THIS lesson. The server lists them (GET /controls: id, kind,
// its current value, a hint) so a switch added in `lessonforge/knobs.py` appears here with no client change.
// Nothing chosen means the server's own value; only what differs is sent (`settings` on POST /generate) and
// recorded on the job. Folded by default: most lessons need none of this.
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { api, Control, ControlList, Settings } from './api';
import { C } from './theme';

export function changedCount(settings: Settings): number {
  return Object.keys(settings).length;
}

export function Controls({ server, value, onChange }: { server: string; value: Settings; onChange: (next: Settings) => void }) {
  const [list, setList] = useState<ControlList | null>(null);
  const [open, setOpen] = useState(false);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  useEffect(() => {
    const request = new AbortController();
    api
      .controls(server, request.signal)
      .then(setList)
      .catch(() => setList(null));
    return () => request.abort();
  }, [server]);
  const byGroup = useMemo(() => {
    const groups = new Map<string, Control[]>();
    (list?.controls ?? []).forEach((control) => {
      const rows = groups.get(control.group) ?? [];
      rows.push(control);
      groups.set(control.group, rows);
    });
    const order = list?.groups ?? [];
    return [...groups.entries()].sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
  }, [list]);
  if (!list || list.controls.length === 0) return null;
  const changed = changedCount(value);
  const set = (control: Control, next: string | null) => {
    const copy = { ...value };
    if (next === null || next === control.current) delete copy[control.id];
    else copy[control.id] = next;
    onChange(copy);
  };
  return (
    <View style={styles.wrap}>
      <Pressable onPress={() => setOpen(!open)} style={styles.head} aria-label="All controls">
        <Text style={styles.title}>All controls</Text>
        <Text style={styles.count}>{changed > 0 ? `${changed} changed` : 'server defaults'}</Text>
        <Text style={styles.arrow}>{open ? '▾' : '▸'}</Text>
      </Pressable>
      {open ? (
        <>
          <Text style={styles.finePrint}>
            Each switch of the pipeline, for this lesson only. Nothing chosen means the server’s own setting, shown as “now”.
            {changed > 0 ? ' ' : ''}
            {changed > 0 ? (
              <Text style={styles.link} onPress={() => onChange({})}>
                Reset all
              </Text>
            ) : null}
          </Text>
          {byGroup.map(([group, rows]) => {
            const changedHere = rows.filter((c) => value[c.id] !== undefined).length;
            const shown = openGroup === group;
            return (
              <View key={group} style={styles.group}>
                <Pressable onPress={() => setOpenGroup(shown ? null : group)} style={styles.groupHead}>
                  <Text style={styles.groupTitle}>{group}</Text>
                  <Text style={styles.count}>{changedHere > 0 ? `${changedHere} changed` : `${rows.length}`}</Text>
                  <Text style={styles.arrow}>{shown ? '▾' : '▸'}</Text>
                </Pressable>
                {shown
                  ? rows.map((control) => (
                      <ControlRow key={control.id} control={control} value={value[control.id]} onChange={(next) => set(control, next)} />
                    ))
                  : null}
              </View>
            );
          })}
        </>
      ) : null}
    </View>
  );
}

function ControlRow({ control, value, onChange }: { control: Control; value: string | undefined; onChange: (next: string | null) => void }) {
  const effective = value ?? control.current;
  const changed = value !== undefined;
  const label = (
    <View style={styles.labelRow}>
      <Text style={[styles.label, changed && styles.labelOn]}>{control.label}</Text>
      {changed ? (
        <Text style={styles.link} onPress={() => onChange(null)}>
          reset
        </Text>
      ) : null}
    </View>
  );
  let body = null;
  if (control.kind === 'toggle') {
    body = (
      <View style={styles.chips}>
        {(['1', '0'] as const).map((v) => (
          <Pressable key={v} onPress={() => onChange(v)} style={[styles.chip, effective === v && styles.chipOn]}>
            <Text style={[styles.chipText, effective === v && styles.chipTextOn]}>
              {v === '1' ? 'On' : 'Off'}
              {control.current === v ? <Text style={styles.now}>{'  now'}</Text> : null}
            </Text>
          </Pressable>
        ))}
      </View>
    );
  } else if (control.kind === 'choice') {
    body = (
      <View style={styles.chips}>
        {(control.options ?? []).map((option) => (
          <Pressable key={option.value} onPress={() => onChange(option.value)} style={[styles.chip, effective === option.value && styles.chipOn]}>
            <Text style={[styles.chipText, effective === option.value && styles.chipTextOn]}>
              {option.label}
              {control.current === option.value ? <Text style={styles.now}>{'  now'}</Text> : null}
            </Text>
          </Pressable>
        ))}
      </View>
    );
  } else if (control.kind === 'number') {
    const n = Number.parseInt(effective, 10);
    const low = control.low ?? 0;
    const high = control.high ?? 99;
    const step = (d: number) => onChange(String(Math.min(high, Math.max(low, (Number.isFinite(n) ? n : low) + d))));
    body = (
      <View style={styles.chips}>
        <Pressable onPress={() => step(-1)} style={styles.chip} aria-label={`${control.label}: less`}>
          <Text style={styles.chipText}>−</Text>
        </Pressable>
        <View style={[styles.chip, changed && styles.chipOn]}>
          <Text style={[styles.chipText, changed && styles.chipTextOn]}>
            {effective}
            {!changed ? <Text style={styles.now}>{'  now'}</Text> : null}
          </Text>
        </View>
        <Pressable onPress={() => step(1)} style={styles.chip} aria-label={`${control.label}: more`}>
          <Text style={styles.chipText}>+</Text>
        </Pressable>
        <Text style={styles.range}>
          {low} to {high}
        </Text>
      </View>
    );
  } else {
    body = (
      <TextInput
        value={effective}
        onChangeText={(text) => onChange(text)}
        onBlur={() => {
          if (value !== undefined && value.trim() === control.current) onChange(null);
        }}
        placeholder={control.current}
        placeholderTextColor={C.muted}
        autoCapitalize="none"
        autoCorrect={false}
        style={[styles.input, changed && styles.inputOn]}
      />
    );
  }
  return (
    <View style={styles.row}>
      {label}
      {body}
      {control.hint ? <Text style={styles.hint}>{control.hint}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8, marginTop: 6 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { color: C.ink, fontSize: 19, fontWeight: '600', flex: 1 },
  count: { color: C.muted, fontSize: 12 },
  arrow: { color: C.muted, fontSize: 14 },
  finePrint: { color: C.muted, fontSize: 12, lineHeight: 18 },
  link: { color: C.teal, textDecorationLine: 'underline', fontSize: 12 },
  group: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 12, gap: 10 },
  groupHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  groupTitle: { color: C.ink, fontSize: 15, fontWeight: '600', flex: 1 },
  row: { gap: 6, borderTopWidth: 1, borderTopColor: C.line, paddingTop: 10 },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  label: { color: C.ink, fontSize: 14, flex: 1 },
  labelOn: { color: C.teal },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.bg, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  chipOn: { borderColor: C.teal },
  chipText: { color: C.muted, fontSize: 13 },
  chipTextOn: { color: C.teal },
  now: { color: C.gold, fontSize: 11 },
  range: { color: C.muted, fontSize: 11 },
  input: { color: C.ink, backgroundColor: C.bg, borderWidth: 1, borderColor: C.line, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, fontSize: 13 },
  inputOn: { borderColor: C.teal },
  hint: { color: C.muted, fontSize: 12, lineHeight: 17 },
});
