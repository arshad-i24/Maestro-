import {
  Clock,
  GraduationCap,
  Drum,
} from "lucide-react";

import StaggerContainer, {
  StaggerItem,
} from "./StaggerContainer";

function WhyMaestro() {
  const reasons = [
    {
      icon: Clock,
      title: "Saves Hours",
      description:
        "Automates manual music transcription and converts recordings into notation faster.",
      accent: "purple",
    },
    {
      icon: GraduationCap,
      title: "Great For Learners",
      description:
        "Helps students and musicians understand songs through readable sheet music.",
      accent: "cyan",
    },
    {
      icon: Drum,
      title: "Supports Indian Music",
      description:
        "Introduces experimental AI-based Tabla transcription capabilities.",
      accent: "purple",
    },
  ];

  return (
    <section
      id="why"
      className="relative px-8 py-28"
    >
      <div className="mx-auto max-w-7xl">

        {/* Section Heading */}
        <StaggerContainer className="mx-auto mb-16 max-w-3xl text-center">
          <StaggerItem>
            <p className="mb-4 text-sm uppercase tracking-[0.2em] text-purple-400">
              Why Maestro
            </p>
          </StaggerItem>

          <StaggerItem>
            <h2 className="text-4xl font-bold text-white md:text-5xl">
              Why Maestro?
            </h2>
          </StaggerItem>

          <StaggerItem>
            <p className="mt-5 text-lg leading-8 text-gray-400">
              Combining artificial intelligence and music technology
              to make transcription faster, more accessible,
              and easier to understand.
            </p>
          </StaggerItem>
        </StaggerContainer>

        {/* Reasons */}
        <StaggerContainer
          className="grid grid-cols-1 gap-6 md:grid-cols-3"
          stagger={0.15}
        >
          {reasons.map((item) => {
            const Icon = item.icon;

            return (
              <StaggerItem key={item.title}>
                <div
                  className="
                    group
                    relative
                    h-full
                    overflow-hidden
                    rounded-3xl
                    border
                    border-white/10
                    bg-[#111111]
                    p-8
                    text-center
                    transition-all
                    duration-500
                    hover:-translate-y-2
                    hover:border-purple-500/40
                    hover:bg-[#141414]
                    hover:shadow-[0_20px_60px_rgba(139,92,246,0.10)]
                  "
                >

                  {/* Background Glow */}
                  <div
                    className={`
                      absolute
                      -top-16
                      left-1/2
                      h-40
                      w-40
                      -translate-x-1/2
                      rounded-full
                      blur-3xl
                      opacity-0
                      transition-opacity
                      duration-500
                      group-hover:opacity-100
                      ${
                        item.accent === "cyan"
                          ? "bg-cyan-400/10"
                          : "bg-purple-500/10"
                      }
                    `}
                  />

                  {/* Icon */}
                  <div
                    className={`
                      relative
                      mx-auto
                      flex
                      h-16
                      w-16
                      items-center
                      justify-center
                      rounded-2xl
                      border
                      transition-all
                      duration-500
                      group-hover:scale-110
                      ${
                        item.accent === "cyan"
                          ? "border-cyan-400/20 bg-cyan-400/5"
                          : "border-purple-400/20 bg-purple-500/10"
                      }
                    `}
                  >
                    <Icon
                      size={30}
                      className={`
                        transition-all
                        duration-500
                        ${
                          item.accent === "cyan"
                            ? "text-cyan-400 group-hover:text-cyan-300"
                            : "text-purple-400 group-hover:text-purple-300"
                        }
                      `}
                    />
                  </div>

                  {/* Content */}
                  <div className="relative">
                    <h3 className="mt-6 text-2xl font-bold text-white">
                      {item.title}
                    </h3>

                    <p className="mt-4 leading-7 text-gray-400">
                      {item.description}
                    </p>
                  </div>

                  {/* Bottom Accent */}
                  <div
                    className={`
                      absolute
                      bottom-0
                      left-10
                      right-10
                      h-px
                      origin-center
                      scale-x-0
                      transition-transform
                      duration-500
                      group-hover:scale-x-100
                      ${
                        item.accent === "cyan"
                          ? "bg-gradient-to-r from-transparent via-cyan-400 to-transparent"
                          : "bg-gradient-to-r from-transparent via-purple-400 to-transparent"
                      }
                    `}
                  />

                </div>
              </StaggerItem>
            );
          })}
        </StaggerContainer>

      </div>
    </section>
  );
}

export default WhyMaestro;