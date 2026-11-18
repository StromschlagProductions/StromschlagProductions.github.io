typedef __SIZE_TYPE__ size_t;
extern unsigned char __heap_base;
static unsigned long heap_ptr = 0;
extern "C" void* malloc(size_t n){ if(!heap_ptr) heap_ptr=(unsigned long)&__heap_base; heap_ptr=(heap_ptr+15)&~15UL; unsigned long p=heap_ptr; heap_ptr+=n;
  unsigned long need=(heap_ptr>>16)+1, have=__builtin_wasm_memory_size(0); if(need>have) __builtin_wasm_memory_grow(0,need-have); return (void*)p; }
extern "C" void free(void*){}
void* operator new(size_t n){return malloc(n);} void* operator new[](size_t n){return malloc(n);}
void operator delete(void*) noexcept {} void operator delete[](void*) noexcept {}
void operator delete(void*, size_t) noexcept {} void operator delete[](void*, size_t) noexcept {}
extern "C" void* memset(void* d,int c,size_t n){unsigned char*p=(unsigned char*)d;while(n--)*p++=(unsigned char)c;return d;}
extern "C" void* memcpy(void* d,const void* s,size_t n){unsigned char*p=(unsigned char*)d;const unsigned char*q=(const unsigned char*)s;while(n--)*p++=*q++;return d;}
extern "C" void* memmove(void* d,const void* s,size_t n){unsigned char*p=(unsigned char*)d;const unsigned char*q=(const unsigned char*)s;if(p<q)while(n--)*p++=*q++;else{p+=n;q+=n;while(n--)*--p=*--q;}return d;}
extern "C" void __cxa_pure_virtual(){ __builtin_trap(); }
extern "C" int __cxa_atexit(void(*)(void*),void*,void*){return 0;}
void* __dso_handle = 0;
