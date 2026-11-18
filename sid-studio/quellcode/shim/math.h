#ifndef SHIM_MATH_H
#define SHIM_MATH_H
extern "C" {
double exp(double); double log(double); double pow(double,double); double sin(double); double cos(double);
double log1p(double); double log10(double); double atan2(double,double); double atan(double); double tan(double); double expm1(double);
}
static inline double sqrt(double x){return __builtin_sqrt(x);}
static inline double floor(double x){return __builtin_floor(x);}
static inline double ceil(double x){return __builtin_ceil(x);}
static inline double fabs(double x){return __builtin_fabs(x);}
static inline double round(double x){return __builtin_round(x);}
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#endif
