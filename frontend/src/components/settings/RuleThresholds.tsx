import { useEffect, useState } from "react";

import { useThresholdInfo, useUpdateSettings } from "../../hooks/queries";
import {
  THRESHOLD_FIELDS,
  toOverrides,
  toThresholdForm,
  validateThresholds,
  type ThresholdForm,
} from "../../utils/thresholds";
import { Button, Card, Input } from "../ui";

const GROUPS = [
  "Do-Not-Trade gate",
  "Portfolio limits",
  "Exit alerts",
] as const;

/** Edit the rule thresholds. Defaults are the documented values; changes are audit-logged. */
export function RuleThresholds() {
  const info = useThresholdInfo();
  const update = useUpdateSettings();
  const [form, setForm] = useState<ThresholdForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (info.data) setForm(toThresholdForm(info.data.effective));
  }, [info.data]);

  if (!info.data || !form) {
    return (
      <Card title="Rule thresholds">
        <p className="text-sm text-gray-500">
          {info.isError ? "Could not load thresholds." : "Loading…"}
        </p>
      </Card>
    );
  }
  const data = info.data;

  const save = (thresholds: ReturnType<typeof toOverrides>) => {
    setSaved(false);
    update.mutate({ thresholds }, { onSuccess: () => setSaved(true) });
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validateThresholds(form, data);
    setError(problem);
    if (!problem) save(toOverrides(form, data.defaults));
  };

  const reset = () => {
    setError(null);
    save({});
  };

  return (
    <form onSubmit={submit} aria-label="Rule thresholds" noValidate>
      <Card
        title="Rule thresholds"
        subtitle="The limits the Do-Not-Trade gate, portfolio checks and exit alerts use. Defaults are the documented values."
      >
        <div className="space-y-5">
          {GROUPS.map((group) => (
            <fieldset key={group}>
              <legend className="mb-2 text-sm font-semibold">{group}</legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {THRESHOLD_FIELDS.filter((f) => f.group === group).map((f) => {
                  const { min, max } = data.bounds[f.key];
                  return (
                    <div key={f.key}>
                      <Input
                        label={`${f.label} (${f.unit})`}
                        type="number"
                        step="any"
                        min={min}
                        max={max}
                        hint={`${f.hint} Default ${data.defaults[f.key]}, allowed ${min} to ${max}.`}
                        value={form[f.key]}
                        onChange={(e) =>
                          setForm({ ...form, [f.key]: e.target.value })
                        }
                      />
                      {data.loosened.includes(f.key) && (
                        <p className="mt-1 text-xs text-amber-700">
                          Looser than the default.
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </fieldset>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button type="submit" loading={update.isPending}>
            Save thresholds
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={reset}
            disabled={update.isPending}
          >
            Reset to defaults
          </Button>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          {saved && !error && <p className="text-sm text-green-700">Saved.</p>}
        </div>
        {data.loosened.length > 0 && (
          <p className="mt-3 text-sm text-amber-700">
            {data.loosened.length} safety rule(s) are set looser than the
            default. The gate will allow trades it would otherwise block.
          </p>
        )}
      </Card>
    </form>
  );
}
