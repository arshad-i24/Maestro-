import { Piano, Guitar, Music, Drum } from "lucide-react";
import StaggerContainer, {
  StaggerItem,
} from "./StaggerContainer";

function Instruments() {
  const instruments = [
    {
      icon: Piano,
      name: "Piano",
      description:
        "will be implemented in future update.",
      accent: "purple",
    },
    {
      icon: Guitar,
      name: "Guitar",
      description:
        "will be implemented in future update.",
      accent: "purple",
    },
    {
      icon: Music,
      name: "Flute",
      description:
        "Create melody-focused notation for flute performances.",
      accent: "cyan",
    },
    {
      icon: Drum,
      name: "Tabla",
      description:
        "will be implemented in future update.",
      accent: "purple",
    },
  ];

  return (
    <section
      id="instruments"
      className="relative px-8 py-28"
    >
      <div className="mx-auto max-w-7xl">

        {/* Section Heading */}
        <StaggerContainer className="mx-auto mb-16 max-w-4xl text-center">
          <StaggerItem>
            <p className="mb-4 text-sm uppercase tracking-[0.2em] text-purple-400">
              Multi-Instrument AI
            </p>
          </StaggerItem>

          <StaggerItem>
            <h2 className="text-4xl font-bold leading-tight text-white md:text-5xl">
              Generate instrument-specific notation for multiple musical
              styles and performances.
            </h2>
          </StaggerItem>

          <StaggerItem>
            <p className="mt-5 text-lg text-gray-400">
              Multi-instrument transcription powered by AI.
            </p>
          </StaggerItem>
        </StaggerContainer>

        {/* Instrument Cards */}
        <StaggerContainer
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4"
          stagger={0.12}
        >
          {instruments.map((item) => {
            const Icon = item.icon;

            return (
              <StaggerItem key={item.name}>
                <div
                  className={`
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
                    hover:shadow-[0_20px_50px_rgba(139,92,246,0.12)]
                    ${
                      item.name === "Guitar"
                        ? "hover:rotate-[1deg]"
                        : ""
                    }
                  `}
                >

                  {/* Background Glow */}
                  <div
                    className={`
                      absolute
                      -right-12
                      -top-12
                      h-32
                      w-32
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

                  {/* Icon Container */}
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
                      ${
                        item.accent === "cyan"
                          ? "border-cyan-400/20 bg-cyan-400/5"
                          : "border-purple-400/20 bg-purple-500/10"
                      }
                      group-hover:scale-110
                      group-hover:shadow-[0_0_30px_rgba(139,92,246,0.15)]
                    `}
                  >
                    <Icon
                      size={32}
                      className={`
                        transition-all
                        duration-500
                        ${
                          item.accent === "cyan"
                            ? "text-cyan-400 group-hover:text-cyan-300"
                            : "text-purple-400 group-hover:text-purple-300"
                        }
                        ${
                          item.name === "Tabla"
                            ? "group-hover:scale-110"
                            : ""
                        }
                      `}
                    />

                    {/* Tabla Pulse */}
                    {item.name === "Tabla" && (
                      <div
                        className="
                          absolute
                          inset-0
                          rounded-2xl
                          border
                          border-purple-400/20
                          opacity-0
                          group-hover:animate-ping
                          group-hover:opacity-100
                        "
                      />
                    )}
                  </div>

                  {/* Content */}
                  <div className="relative">
                    <h3 className="mt-6 text-2xl font-bold text-white">
                      {item.name}
                    </h3>

                    <p className="mt-3 text-sm leading-7 text-gray-400">
                      {item.description}
                    </p>
                  </div>

                  {/* Bottom Accent */}
                  <div
                    className={`
                      absolute
                      bottom-0
                      left-8
                      right-8
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

export default Instruments;