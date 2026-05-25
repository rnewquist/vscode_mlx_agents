import { SparkleIcon } from "./Icons";

interface WelcomeScreenProps {
  onSuggestion: (text: string) => void;
}

const suggestions = [
  "Explain this code",
  "Refactor the selected function",
  "Write unit tests",
  "Fix the bug in my selection",
  "Summarize this file",
];

export function WelcomeScreen({ onSuggestion }: WelcomeScreenProps) {
  return (
    <div className="welcome-screen">
      <div className="welcome-icon">
        <SparkleIcon size={32} />
      </div>
      <h2 className="welcome-title">MLX Agent</h2>
      <p className="welcome-subtitle">
        Talk directly to your local model running on Apple Silicon.
      </p>
      <div className="suggestion-chips">
        {suggestions.map((s) => (
          <button
            key={s}
            className="suggestion-chip"
            onClick={() => onSuggestion(s)}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
