"use client";

import { CheckCircleIcon } from "@heroicons/react/20/solid";
import clsx from "clsx";
import type { OnboardingStepState } from "../model/types";

interface OnboardingStepperProps {
  steps: OnboardingStepState[];
  currentStep: number;
  onSelectStep: (index: number) => void;
}

export function OnboardingStepper({
  steps,
  currentStep,
  onSelectStep,
}: OnboardingStepperProps) {
  return (
    <ol className="flex flex-col gap-2 md:flex-row md:items-start md:gap-0">
      {steps.map((step, index) => {
        const isCurrent = index === currentStep;
        const isReachable = index <= currentStep || step.complete;
        return (
          <li
            key={step.id}
            className={clsx(
              "flex items-start gap-2 md:flex-1 md:flex-col md:items-center md:text-center",
              !isReachable && "opacity-60"
            )}
          >
            <button
              type="button"
              disabled={!isReachable}
              onClick={() => isReachable && onSelectStep(index)}
              className={clsx(
                "flex items-center gap-2 rounded-lg px-2 py-1 text-left md:flex-col md:px-1",
                isCurrent && "bg-orange-50"
              )}
            >
              <span
                className={clsx(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  step.complete
                    ? "bg-emerald-500 text-white"
                    : isCurrent
                      ? "bg-orange-500 text-white"
                      : "bg-gray-200 text-gray-700"
                )}
                aria-current={isCurrent ? "step" : undefined}
              >
                {step.complete ? (
                  <CheckCircleIcon className="h-5 w-5" />
                ) : (
                  index + 1
                )}
              </span>
              <span className="text-xs font-medium text-gray-800">
                {step.shortTitle}
              </span>
            </button>
            {index < steps.length - 1 && (
              <span className="hidden h-px w-full bg-gray-200 md:block" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
