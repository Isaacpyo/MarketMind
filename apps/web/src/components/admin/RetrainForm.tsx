"use client";

import { FlaskConical, LoaderCircle } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api/client";
import type { AlsParams } from "@/lib/api/types";
import { formatDuration } from "@/lib/format";
import { useRetrain } from "@/lib/hooks";

export const PARAM_FIELDS: {
  key: keyof AlsParams;
  label: string;
  min: number;
  max: number;
  step: number;
  help: string;
}[] = [
  { key: "factors", label: "Latent factors", min: 8, max: 256, step: 8, help: "Size of the user/item vectors" },
  { key: "regularization", label: "Regularisation", min: 0.0001, max: 10, step: 0.01, help: "L2 penalty (λ)" },
  { key: "alpha", label: "Confidence α", min: 0.05, max: 100, step: 0.05, help: "Weight on observed interactions" },
  { key: "iterations", label: "Iterations", min: 1, max: 50, step: 1, help: "ALS sweeps" },
  { key: "hybrid_weight", label: "Hybrid ALS weight", min: 0, max: 1, step: 0.05, help: "ALS vs content in the feed" },
];

/** Returns an error message per invalid field (mirrors the API's bounds). */
export function validateParams(values: Record<keyof AlsParams, string>): Partial<Record<keyof AlsParams, string>> {
  const errors: Partial<Record<keyof AlsParams, string>> = {};
  for (const field of PARAM_FIELDS) {
    const raw = values[field.key];
    const n = Number(raw);
    if (raw.trim() === "" || !Number.isFinite(n)) errors[field.key] = "Enter a number";
    else if (n < field.min || n > field.max) errors[field.key] = `Between ${field.min} and ${field.max}`;
    else if ((field.key === "factors" || field.key === "iterations") && !Number.isInteger(n))
      errors[field.key] = "Whole numbers only";
  }
  return errors;
}

export function RetrainForm({
  defaults,
  running,
  cooldownSeconds,
}: {
  defaults: AlsParams;
  running: boolean;
  cooldownSeconds: number;
}) {
  const retrain = useRetrain();
  const baseId = useId();
  const [values, setValues] = useState<Record<keyof AlsParams, string>>(() => ({
    factors: String(defaults.factors),
    regularization: String(defaults.regularization),
    alpha: String(defaults.alpha),
    iterations: String(defaults.iterations),
    hybrid_weight: String(defaults.hybrid_weight),
  }));
  const [errors, setErrors] = useState<Partial<Record<keyof AlsParams, string>>>({});

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateParams(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    retrain.mutate({
      factors: Number(values.factors),
      regularization: Number(values.regularization),
      alpha: Number(values.alpha),
      iterations: Number(values.iterations),
      hybrid_weight: Number(values.hybrid_weight),
    });
  }

  const disabled = running || retrain.isPending || cooldownSeconds > 0;
  return (
    <form onSubmit={onSubmit} className="card space-y-4 p-5" aria-labelledby={`${baseId}-title`} noValidate>
      <div>
        <h2 id={`${baseId}-title`} className="text-lg font-semibold">
          Retrain the model
        </h2>
        <p className="mt-0.5 text-sm text-slate-600">
          Runs in the background: holdout evaluation, then a refit on all data including new live events. The new
          model is hot-swapped in.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        {PARAM_FIELDS.map((field) => {
          const id = `${baseId}-${field.key}`;
          const error = errors[field.key];
          return (
            <div key={field.key}>
              <label htmlFor={id} className="label">
                {field.label}
              </label>
              <input
                id={id}
                type="number"
                inputMode="decimal"
                className="input"
                min={field.min}
                max={field.max}
                step={field.step}
                value={values[field.key]}
                aria-invalid={Boolean(error)}
                aria-describedby={`${id}-help`}
                onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
              />
              <p id={`${id}-help`} className={error ? "mt-1 text-xs text-rose-700" : "mt-1 text-xs text-slate-500"}>
                {error ?? field.help}
              </p>
            </div>
          );
        })}
      </div>
      <button type="submit" className="btn-primary w-full" disabled={disabled}>
        {running || retrain.isPending ? (
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <FlaskConical className="size-4" aria-hidden="true" />
        )}
        {running ? "Training…" : cooldownSeconds > 0 ? `Available in ${formatDuration(cooldownSeconds)}` : "Retrain model"}
      </button>
      <div aria-live="polite">
        {retrain.error ? (
          <p role="alert" className="text-sm text-rose-700">
            {retrain.error instanceof ApiError ? retrain.error.message : "Couldn't start training."}
          </p>
        ) : null}
      </div>
    </form>
  );
}
